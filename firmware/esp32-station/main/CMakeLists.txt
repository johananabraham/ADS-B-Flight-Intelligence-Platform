set(BROKER_CA "${CMAKE_CURRENT_LIST_DIR}/../certs/broker_ca.pem")
if(NOT EXISTS "${BROKER_CA}")
    message(FATAL_ERROR "Missing certs/broker_ca.pem; copy the CA created by scripts/provision_edge_mqtt.sh")
endif()

idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES esp_event esp_netif esp_timer esp_wifi nvs_flash esp_system
    EMBED_TXTFILES "${BROKER_CA}"
)
