# chatbot/core/vector_index.py

from langchain_community.vectorstores import Neo4jVector
from neo4j import GraphDatabase

from .embeddings import EmbeddingHuggingFace
from utils.config import settings
from utils._logger import get_logger

logger = get_logger("chatbot.core.vector_index", log_file="logs/chatbot/core/vector_index.log")

def clean_index_name(index_name: str):
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run(f"""DROP INDEX {index_name} IF EXISTS""")
            logger.info(f"Index '{index_name}' dropped successfully before creation.")

    except Exception as e:
        logger.warning(f"Index '{index_name}' could not be dropped or does not exist: {e}", exc_info=True)
    finally:
        if driver:
            driver.close()        
            

def create_vector_index(node_label: str, properties: list, index_name: str) -> Neo4jVector:
    """
    Create a Neo4j vector index for a specific node label and properties.
    
    Args:
        node_label: The label of the nodes to index.
        properties: List of node properties to use for text representation.
        index_name: Name of the vector index to create.
    """

    clean_index_name(index_name)

    try:
        embeddings = EmbeddingHuggingFace()
    except Exception as e:
        logger.error(f"Failed to initialize embeddings: {e}", exc_info=True)
        return None

    try:
        vector_store = Neo4jVector.from_existing_graph(
            embedding=embeddings,
            url=settings.NEO4J_URI,
            username=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
            database=settings.NEO4J_DATABASE,
            index_name=index_name,
            node_label=node_label,
            text_node_properties=properties,
            embedding_node_property="embedding",
        )

        logger.info(f"Vector index '{index_name}' created for node label '{node_label}' with properties {properties}")
        return vector_store
    except Exception as e:
        logger.error(f"Error creating vector index '{index_name}': {e}", exc_info=True)
        return None


if __name__ == "__main__":
    # Politician vector index
    create_vector_index(
        node_label="Politician",
        properties=["full_text_summary"],
        index_name="politician_vector_index"
    )

    # Position vector index
    create_vector_index(
        node_label="Position",
        properties=["name"],
        index_name="position_vector_index"
    )

    # Location vector index
    create_vector_index(
        node_label="Location",
        properties=["name"],
        index_name="location_vector_index"
    )

    # Award vector index
    create_vector_index(
        node_label="Award",
        properties=["name"],
        index_name="award_vector_index"
    )

    # MilitaryCareer vector index
    create_vector_index(
        node_label="MilitaryCareer",
        properties=["name"],
        index_name="militarycareer_vector_index"
    )

    # MiliteryRank vector index
    create_vector_index(
        node_label="MilitaryRank",
        properties=["name"],
        index_name="militaryrank_vector_index"
    )

    # Campaigns vector index
    create_vector_index(
        node_label="Campaigns",
        properties=["name"],
        index_name="campaigns_vector_index"
    )

    # AlmaMater vector index
    create_vector_index(
        node_label="AlmaMater",
        properties=["name"],
        index_name="almamater_vector_index"
    )

    # AcademicTitle vector index
    create_vector_index(
        node_label="AcademicTitle",
        properties=["name"],
        index_name="academictitle_vector_index"
    )

    # RelationChunk
    create_vector_index(
        node_label="RelationChunk",
        properties=["text_for_embedding"],
        index_name="relationchunk_vector_index"
    )
