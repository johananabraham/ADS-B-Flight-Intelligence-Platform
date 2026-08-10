"""ChromaDB vector store for semantic search over safety data."""

import logging
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from .config import get_settings

logger = logging.getLogger(__name__)

# Global ChromaDB client
_chroma_client: Optional[chromadb.ClientAPI] = None

# Collection names
INCIDENT_NARRATIVES_COLLECTION = "incident_narratives"
FAA_REGULATIONS_COLLECTION = "faa_regulations"

# Use ChromaDB's default embedding function (all-MiniLM-L6-v2)
_default_ef = embedding_functions.DefaultEmbeddingFunction()


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or create the ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        settings = get_settings()
        persist_dir = Path(settings.chroma_persist_directory)
        persist_dir.mkdir(parents=True, exist_ok=True)

        _chroma_client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        logger.info(f"ChromaDB client initialized with persistence at {persist_dir}")
    return _chroma_client


def get_incident_narratives_collection() -> chromadb.Collection:
    """Get or create the incident narratives collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=INCIDENT_NARRATIVES_COLLECTION,
        embedding_function=_default_ef,
        metadata={
            "description": "NTSB incident narrative text for semantic search",
            "hnsw:space": "cosine",
        },
    )


def get_faa_regulations_collection() -> chromadb.Collection:
    """Get or create the FAA regulations collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=FAA_REGULATIONS_COLLECTION,
        embedding_function=_default_ef,
        metadata={
            "description": "FAA 14 CFR regulation sections for semantic search",
            "hnsw:space": "cosine",
        },
    )


async def search_incident_narratives(
    query_text: str,
    n_results: int = 5,
    where: Optional[dict[str, Any]] = None,
    where_document: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Search incident narratives by text similarity.

    Args:
        query_text: The search query text
        n_results: Number of results to return
        where: Metadata filter conditions
        where_document: Document content filter conditions

    Returns:
        Dictionary with ids, documents, metadatas, and distances
    """
    collection = get_incident_narratives_collection()

    query_params: dict[str, Any] = {
        "query_texts": [query_text],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }

    if where:
        query_params["where"] = where
    if where_document:
        query_params["where_document"] = where_document

    results = collection.query(**query_params)

    return {
        "ids": results["ids"][0] if results["ids"] else [],
        "documents": results["documents"][0] if results["documents"] else [],
        "metadatas": results["metadatas"][0] if results["metadatas"] else [],
        "distances": results["distances"][0] if results["distances"] else [],
    }


async def search_faa_regulations(
    query_text: str,
    n_results: int = 5,
    where: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Search FAA regulations by text similarity.

    Args:
        query_text: The search query text
        n_results: Number of results to return
        where: Metadata filter conditions (e.g., {"cfr_part": 91})

    Returns:
        Dictionary with ids, documents, metadatas, and distances
    """
    collection = get_faa_regulations_collection()

    query_params: dict[str, Any] = {
        "query_texts": [query_text],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }

    if where:
        query_params["where"] = where

    results = collection.query(**query_params)

    return {
        "ids": results["ids"][0] if results["ids"] else [],
        "documents": results["documents"][0] if results["documents"] else [],
        "metadatas": results["metadatas"][0] if results["metadatas"] else [],
        "distances": results["distances"][0] if results["distances"] else [],
    }


def add_incident_narratives(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    """
    Add incident narratives to the collection.

    Args:
        ids: Unique identifiers (typically ntsb_id + chunk_index)
        documents: Text chunks
        metadatas: Metadata for each chunk
    """
    collection = get_incident_narratives_collection()
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )
    logger.debug(f"Added {len(ids)} incident narrative chunks to ChromaDB")


def delete_incident_narratives(ntsb_id: str) -> None:
    """Remove every prior chunk for one incident before replacing its document set."""
    collection = get_incident_narratives_collection()
    collection.delete(where={"ntsb_id": ntsb_id})


def add_faa_regulations(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    """
    Add FAA regulations to the collection.

    Args:
        ids: Unique identifiers (e.g., "14_CFR_91.103_chunk_0")
        documents: Text chunks
        metadatas: Metadata for each chunk
    """
    collection = get_faa_regulations_collection()
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )
    logger.debug(f"Added {len(ids)} FAA regulation chunks to ChromaDB")


def check_vectorstore_health() -> dict[str, Any]:
    """Check ChromaDB health and return status."""
    try:
        client = get_chroma_client()
        collections = client.list_collections()

        incident_count = 0
        regulation_count = 0

        for col in collections:
            if col.name == INCIDENT_NARRATIVES_COLLECTION:
                incident_count = col.count()
            elif col.name == FAA_REGULATIONS_COLLECTION:
                regulation_count = col.count()

        return {
            "status": "healthy",
            "vectorstore": "connected",
            "collections": {
                "incident_narratives": incident_count,
                "faa_regulations": regulation_count,
            },
        }
    except Exception as e:
        logger.error(f"Vectorstore health check failed: {e}")
        return {"status": "unhealthy", "vectorstore": str(e)}


def get_collection_stats() -> dict[str, int]:
    """Get document counts for all collections."""
    client = get_chroma_client()

    stats = {}
    try:
        incident_col = client.get_collection(INCIDENT_NARRATIVES_COLLECTION)
        stats["incident_narratives"] = incident_col.count()
    except Exception:
        stats["incident_narratives"] = 0

    try:
        regulation_col = client.get_collection(FAA_REGULATIONS_COLLECTION)
        stats["faa_regulations"] = regulation_col.count()
    except Exception:
        stats["faa_regulations"] = 0

    return stats
