#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_random.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "freertos/timers.h"
#include "mqtt_client.h"
#include "nvs_flash.h"

#define WIFI_CONNECTED_BIT BIT0
#define MQTT_CONNECTED_BIT BIT1
#define TELEMETRY_QUEUE_CAPACITY 16
#define TELEMETRY_PAYLOAD_CAPACITY 768
#define TOPIC_CAPACITY 128
#define PRESENCE_PAYLOAD_CAPACITY 384
#define MAX_WIFI_BACKOFF_SECONDS 60

extern const uint8_t broker_ca_pem_start[] asm("_binary_broker_ca_pem_start");

typedef struct {
    char payload[TELEMETRY_PAYLOAD_CAPACITY];
} telemetry_message_t;

static const char *TAG = "edge-station";
static EventGroupHandle_t connectivity_events;
static QueueHandle_t telemetry_queue;
static TimerHandle_t wifi_reconnect_timer;
static esp_mqtt_client_handle_t mqtt_client;
static atomic_uint_fast32_t reconnect_count;
static atomic_uint_fast64_t sequence_number;
static uint32_t wifi_backoff_seconds = 1;
static char boot_id[37];
static char telemetry_topic[TOPIC_CAPACITY];
static char presence_topic[TOPIC_CAPACITY];
static char offline_presence[PRESENCE_PAYLOAD_CAPACITY];

static void make_uuid(char output[37])
{
    uint8_t bytes[16];
    esp_fill_random(bytes, sizeof(bytes));
    bytes[6] = (bytes[6] & 0x0fU) | 0x40U;
    bytes[8] = (bytes[8] & 0x3fU) | 0x80U;
    snprintf(output, 37,
             "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
             bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5],
             bytes[6], bytes[7], bytes[8], bytes[9], bytes[10], bytes[11],
             bytes[12], bytes[13], bytes[14], bytes[15]);
}

static bool node_id_is_safe(const char *node_id)
{
    size_t length = strlen(node_id);
    if (length == 0 || length > 64) {
        return false;
    }
    for (size_t index = 0; index < length; ++index) {
        char value = node_id[index];
        bool allowed = (value >= 'a' && value <= 'z') ||
                       (value >= 'A' && value <= 'Z') ||
                       (value >= '0' && value <= '9') || value == '-' ||
                       value == '_';
        if (!allowed) {
            return false;
        }
    }
    return true;
}

static bool format_utc_now(char output[21])
{
    time_t now;
    struct tm utc;
    time(&now);
    if (now < 1704067200 || gmtime_r(&now, &utc) == NULL) {
        return false;
    }
    return strftime(output, 21, "%Y-%m-%dT%H:%M:%SZ", &utc) == 20;
}

static bool reset_was_watchdog(void)
{
    esp_reset_reason_t reason = esp_reset_reason();
    return reason == ESP_RST_INT_WDT || reason == ESP_RST_TASK_WDT ||
           reason == ESP_RST_WDT;
}

static void queue_latest(const telemetry_message_t *message)
{
    if (xQueueSend(telemetry_queue, message, 0) == pdTRUE) {
        return;
    }
    telemetry_message_t discarded;
    (void)xQueueReceive(telemetry_queue, &discarded, 0);
    if (xQueueSend(telemetry_queue, message, 0) != pdTRUE) {
        ESP_LOGE(TAG, "bounded telemetry queue remained full");
    } else {
        ESP_LOGW(TAG, "dropped oldest telemetry sample because queue was full");
    }
}

static bool build_presence(char *output, size_t capacity, const char *status,
                           const char *reason)
{
    char message_id[37];
    char observed_at[21];
    make_uuid(message_id);
    if (!format_utc_now(observed_at)) {
        return false;
    }
    int written = snprintf(
        output, capacity,
        "{\"schema_version\":\"1.0\",\"message_id\":\"%s\","
        "\"node_id\":\"%s\",\"observed_at\":\"%s\","
        "\"status\":\"%s\",\"reason\":\"%s\"}",
        message_id, CONFIG_EDGE_NODE_ID, observed_at, status, reason);
    return written > 0 && (size_t)written < capacity;
}

static bool build_telemetry(telemetry_message_t *message)
{
    char message_id[37];
    char observed_at[21];
    wifi_ap_record_t access_point = {0};
    int rssi = -127;
    if (esp_wifi_sta_get_ap_info(&access_point) == ESP_OK) {
        rssi = access_point.rssi;
    }
    make_uuid(message_id);
    if (!format_utc_now(observed_at)) {
        return false;
    }
    uint64_t sequence = atomic_fetch_add(&sequence_number, 1);
    unsigned int queue_depth = uxQueueMessagesWaiting(telemetry_queue);
    int written = snprintf(
        message->payload, sizeof(message->payload),
        "{\"schema_version\":\"1.0\",\"message_id\":\"%s\","
        "\"node_id\":\"%s\",\"firmware_version\":\"%s\","
        "\"boot_id\":\"%s\",\"sequence\":%llu,"
        "\"observed_at\":\"%s\",\"uptime_seconds\":%llu,"
        "\"reconnect_count\":%lu,\"wifi_rssi_dbm\":%d,"
        "\"free_heap_bytes\":%lu,\"queue_depth\":%u,"
        "\"watchdog_reset_detected\":%s}",
        message_id, CONFIG_EDGE_NODE_ID, CONFIG_EDGE_FIRMWARE_VERSION, boot_id,
        (unsigned long long)sequence, observed_at,
        (unsigned long long)(esp_timer_get_time() / 1000000),
        (unsigned long)atomic_load(&reconnect_count), rssi,
        (unsigned long)esp_get_free_heap_size(), queue_depth,
        reset_was_watchdog() ? "true" : "false");
    return written > 0 && (size_t)written < sizeof(message->payload);
}

static void wifi_reconnect_callback(TimerHandle_t timer)
{
    (void)timer;
    esp_err_t result = esp_wifi_connect();
    if (result != ESP_OK) {
        ESP_LOGW(TAG, "Wi-Fi reconnect request failed: %s", esp_err_to_name(result));
    }
}

static void wifi_event_handler(void *argument, esp_event_base_t base,
                               int32_t event_id, void *event_data)
{
    (void)argument;
    (void)event_data;
    if (base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        ESP_ERROR_CHECK(esp_wifi_connect());
    } else if (base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(connectivity_events,
                             WIFI_CONNECTED_BIT | MQTT_CONNECTED_BIT);
        atomic_fetch_add(&reconnect_count, 1);
        TickType_t delay = pdMS_TO_TICKS(wifi_backoff_seconds * 1000U);
        (void)xTimerChangePeriod(wifi_reconnect_timer, delay, 0);
        if (wifi_backoff_seconds < MAX_WIFI_BACKOFF_SECONDS) {
            wifi_backoff_seconds *= 2;
            if (wifi_backoff_seconds > MAX_WIFI_BACKOFF_SECONDS) {
                wifi_backoff_seconds = MAX_WIFI_BACKOFF_SECONDS;
            }
        }
    } else if (base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        (void)xTimerStop(wifi_reconnect_timer, 0);
        wifi_backoff_seconds = 1;
        xEventGroupSetBits(connectivity_events, WIFI_CONNECTED_BIT);
    }
}

static void mqtt_event_handler(void *argument, esp_event_base_t base,
                               int32_t event_id, void *event_data)
{
    (void)argument;
    (void)base;
    (void)event_data;
    if (event_id == MQTT_EVENT_CONNECTED) {
        char online[PRESENCE_PAYLOAD_CAPACITY];
        xEventGroupSetBits(connectivity_events, MQTT_CONNECTED_BIT);
        if (build_presence(online, sizeof(online), "online", "connected")) {
            (void)esp_mqtt_client_enqueue(mqtt_client, presence_topic, online, 0,
                                          1, 1, true);
        }
    } else if (event_id == MQTT_EVENT_DISCONNECTED) {
        xEventGroupClearBits(connectivity_events, MQTT_CONNECTED_BIT);
        atomic_fetch_add(&reconnect_count, 1);
    } else if (event_id == MQTT_EVENT_ERROR) {
        ESP_LOGW(TAG, "MQTT transport error; automatic reconnect will retry");
    }
}

static void initialize_wifi(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t initialization = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&initialization));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                               wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                               wifi_event_handler, NULL));

    wifi_config_t configuration = {0};
    strlcpy((char *)configuration.sta.ssid, CONFIG_EDGE_WIFI_SSID,
            sizeof(configuration.sta.ssid));
    strlcpy((char *)configuration.sta.password, CONFIG_EDGE_WIFI_PASSWORD,
            sizeof(configuration.sta.password));
    configuration.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    configuration.sta.failure_retry_cnt = 3;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &configuration));
    ESP_ERROR_CHECK(esp_wifi_start());
}

static void synchronize_clock(void)
{
    esp_sntp_config_t configuration = ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");
    ESP_ERROR_CHECK(esp_netif_sntp_init(&configuration));
    while (esp_netif_sntp_sync_wait(pdMS_TO_TICKS(30000)) != ESP_OK) {
        ESP_LOGW(TAG, "waiting for trusted UTC time before publishing");
    }
}

static void initialize_mqtt(void)
{
    if (!build_presence(offline_presence, sizeof(offline_presence), "offline",
                        "mqtt-last-will")) {
        ESP_LOGE(TAG, "could not build MQTT last-will payload");
        abort();
    }
    const esp_mqtt_client_config_t configuration = {
        .broker = {
            .address.uri = CONFIG_EDGE_MQTT_URI,
            .verification.certificate = (const char *)broker_ca_pem_start,
        },
        .credentials = {
            .username = CONFIG_EDGE_MQTT_USERNAME,
            .authentication.password = CONFIG_EDGE_MQTT_PASSWORD,
        },
        .session = {
            .keepalive = 60,
            .disable_clean_session = true,
            .last_will = {
                .topic = presence_topic,
                .msg = offline_presence,
                .qos = 1,
                .retain = 1,
            },
        },
        .network.reconnect_timeout_ms = 5000,
    };
    mqtt_client = esp_mqtt_client_init(&configuration);
    if (mqtt_client == NULL) {
        ESP_LOGE(TAG, "could not initialize MQTT client");
        abort();
    }
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(
        mqtt_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(mqtt_client));
}

static void telemetry_task(void *argument)
{
    (void)argument;
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    while (true) {
        telemetry_message_t message = {0};
        if (build_telemetry(&message)) {
            queue_latest(&message);
        } else {
            ESP_LOGW(TAG, "telemetry sample was not created");
        }
        for (int elapsed = 0; elapsed < CONFIG_EDGE_TELEMETRY_INTERVAL_SECONDS;
             ++elapsed) {
            ESP_ERROR_CHECK(esp_task_wdt_reset());
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
}

static void publisher_task(void *argument)
{
    (void)argument;
    telemetry_message_t message;
    while (true) {
        xEventGroupWaitBits(connectivity_events, MQTT_CONNECTED_BIT, pdFALSE,
                            pdTRUE, portMAX_DELAY);
        if (xQueueReceive(telemetry_queue, &message, pdMS_TO_TICKS(1000)) !=
            pdTRUE) {
            continue;
        }
        int message_id = esp_mqtt_client_enqueue(
            mqtt_client, telemetry_topic, message.payload, 0, 1, 0, true);
        if (message_id < 0) {
            ESP_LOGW(TAG, "MQTT outbox rejected telemetry; retrying later");
            (void)xQueueSendToFront(telemetry_queue, &message, 0);
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
}

void app_main(void)
{
    if (!node_id_is_safe(CONFIG_EDGE_NODE_ID) ||
        strcmp(CONFIG_EDGE_NODE_ID, CONFIG_EDGE_MQTT_USERNAME) != 0) {
        ESP_LOGE(TAG, "node ID must be topic-safe and equal the MQTT username");
        abort();
    }
    esp_err_t storage_result = nvs_flash_init();
    if (storage_result == ESP_ERR_NVS_NO_FREE_PAGES ||
        storage_result == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        storage_result = nvs_flash_init();
    }
    ESP_ERROR_CHECK(storage_result);

    connectivity_events = xEventGroupCreate();
    telemetry_queue = xQueueCreate(TELEMETRY_QUEUE_CAPACITY,
                                   sizeof(telemetry_message_t));
    wifi_reconnect_timer = xTimerCreate("wifi-reconnect", pdMS_TO_TICKS(1000),
                                        pdFALSE, NULL, wifi_reconnect_callback);
    if (connectivity_events == NULL || telemetry_queue == NULL ||
        wifi_reconnect_timer == NULL) {
        ESP_LOGE(TAG, "could not allocate station runtime resources");
        abort();
    }
    make_uuid(boot_id);
    snprintf(telemetry_topic, sizeof(telemetry_topic),
             "adsb/stations/v1/%s/telemetry", CONFIG_EDGE_NODE_ID);
    snprintf(presence_topic, sizeof(presence_topic),
             "adsb/stations/v1/%s/presence", CONFIG_EDGE_NODE_ID);

    initialize_wifi();
    xEventGroupWaitBits(connectivity_events, WIFI_CONNECTED_BIT, pdFALSE,
                        pdTRUE, portMAX_DELAY);
    synchronize_clock();
    initialize_mqtt();
    BaseType_t telemetry_created =
        xTaskCreate(telemetry_task, "telemetry", 4096, NULL, 5, NULL);
    BaseType_t publisher_created =
        xTaskCreate(publisher_task, "publisher", 4096, NULL, 5, NULL);
    if (telemetry_created != pdPASS || publisher_created != pdPASS) {
        ESP_LOGE(TAG, "could not create station worker tasks");
        abort();
    }
}
