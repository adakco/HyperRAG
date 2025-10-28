"""
Knowledge Graph Service
Extracts entities and relationships from documents and stores in Neo4j
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from fastapi.responses import Response
from neo4j import GraphDatabase
import spacy

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Configure OpenTelemetry
resource = Resource.create(attributes={SERVICE_NAME: "hyperrag-graph-kg"})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="http://192.168.2.23:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Prometheus metrics
registry = CollectorRegistry()
graph_operation_counter = Counter(
    'hyperrag_graph_operations_total',
    'Total number of graph operations',
    ['tenant', 'operation', 'status'],
    registry=registry
)

graph_operation_duration = Histogram(
    'hyperrag_graph_operation_duration_seconds',
    'Time spent on graph operations',
    ['tenant', 'operation'],
    registry=registry
)


class Settings(BaseSettings):
    """Application settings"""
    neo4j_uri: str = "bolt://192.168.2.23:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "Adakpro123"
    service_name: str = "graph.kg"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"


class Entity(BaseModel):
    """Entity model"""
    entity_id: str
    label: str
    type: str  # PERSON, ORG, LOCATION, etc.
    properties: Dict[str, Any] = Field(default_factory=dict)


class Relationship(BaseModel):
    """Relationship model"""
    relationship_id: str
    from_entity: str
    to_entity: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphExtractionRequest(BaseModel):
    """Request model for graph extraction"""
    doc_id: str
    content: str
    tenant: str
    lang: str = "en"


class GraphExtractionResponse(BaseModel):
    """Response model for graph extraction"""
    doc_id: str
    entities_count: int
    relationships_count: int
    entities: List[Entity]
    relationships: List[Relationship]


class GraphQueryRequest(BaseModel):
    """Request model for graph queries"""
    query: str
    tenant: str
    max_results: int = 10


class GraphQueryResponse(BaseModel):
    """Response model for graph queries"""
    results: List[Dict[str, Any]]
    total: int


class EntityExtractor:
    """Extracts entities from text using spaCy"""
    
    def __init__(self):
        self.models = {}
    
    async def initialize(self):
        """Initialize spaCy models"""
        try:
            self.models['en'] = spacy.load("en_core_web_sm")
            logger.info("English spaCy model loaded")
        except Exception as e:
            logger.warning(f"Could not load spaCy model: {e}")
            logger.info("Using simple entity extraction as fallback")
    
    def extract_entities(self, text: str, lang: str = "en") -> List[Entity]:
        """Extract entities from text"""
        entities = []
        
        try:
            if lang in self.models:
                doc = self.models[lang](text)
                for ent in doc.ents:
                    entity = Entity(
                        entity_id=str(uuid.uuid4()),
                        label=ent.text,
                        type=ent.label_,
                        properties={"start_char": str(ent.start_char), "end_char": str(ent.end_char), "confidence": "0.9"}
                    )
                    entities.append(entity)
        except Exception as e:
            logger.warning(f"spaCy entity extraction failed: {e}")
            # Fallback: simple extraction
            entities = self._simple_entity_extraction(text)
        
        return entities
    
    def _simple_entity_extraction(self, text: str) -> List[Entity]:
        """Simple fallback entity extraction using keywords"""
        entities = []
        
        # Extract potential entities based on capitalization
        import re
        # Look for capitalized phrases (potential entities)
        potential_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        
        for entity_text in set(potential_entities):
            # Skip common words
            if entity_text.lower() in ['the', 'is', 'are', 'was', 'were', 'and', 'or']:
                continue
            
            entity = Entity(
                entity_id=str(uuid.uuid4()),
                label=entity_text,
                type="ORG",  # Default type
                properties={"confidence": "0.6", "method": "pattern_based"}
            )
            entities.append(entity)
        
        return entities
    
    def extract_relationships(self, text: str, entities: List[Entity]) -> List[Relationship]:
        """Extract relationships between entities"""
        relationships = []
        
        # Simple co-occurrence based relationships
        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                # Check if entities co-occur in same sentence
                relationship = Relationship(
                    relationship_id=str(uuid.uuid4()),
                    from_entity=e1.entity_id,
                    to_entity=e2.entity_id,
                    type="RELATED_TO",
                    properties={"confidence": "0.7"}
                )
                relationships.append(relationship)
        
        return relationships


class KnowledgeGraphService:
    """Main knowledge graph service"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.driver = None
        self.extractor = EntityExtractor()
    
    async def initialize(self):
        """Initialize Neo4j driver and entity extractor"""
        self.driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password)
        )
        
        await self.extractor.initialize()
        
        # Create indexes
        with self.driver.session() as session:
            session.run("""
                CREATE CONSTRAINT entity_id IF NOT EXISTS
                FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE
            """)
            session.run("""
                CREATE INDEX entity_type IF NOT EXISTS
                FOR (e:Entity) ON (e.type)
            """)
        
        logger.info("Knowledge graph service initialized")
    
    async def close(self):
        """Close connections"""
        if self.driver:
            await self.driver.close()
    
    async def extract_and_store(
        self,
        request: GraphExtractionRequest
    ) -> GraphExtractionResponse:
        """Extract entities and relationships, store in Neo4j"""
        
        with tracer.start_as_current_span("extract_and_store") as span:
            span.set_attribute("doc_id", request.doc_id)
            span.set_attribute("tenant", request.tenant)
            
            # Extract entities
            entities = self.extractor.extract_entities(request.content, request.lang)
            
            # Extract relationships
            relationships = self.extractor.extract_relationships(
                request.content, entities
            )
            
            # Store in Neo4j
            session = self.driver.session()
            try:
                # Store entities
                for entity in entities:
                    # Convert properties dict to simple key-value pairs (primitive types only)
                    simple_props = {}
                    for key, value in entity.properties.items():
                        # Convert complex types to strings
                        if isinstance(value, (dict, list)):
                            simple_props[key] = json.dumps(value)
                        else:
                            simple_props[key] = str(value) if not isinstance(value, (str, int, float, bool)) else value
                    
                    session.run(
                        """
                        MERGE (e:Entity {entity_id: $entity_id})
                        SET e.label = $label,
                            e.type = $type,
                            e.properties_text = $properties,
                            e.doc_id = $doc_id,
                            e.tenant = $tenant
                        """,
                        entity_id=entity.entity_id,
                        label=entity.label,
                        type=entity.type,
                        properties=json.dumps(simple_props),
                        doc_id=request.doc_id,
                        tenant=request.tenant
                    )
                
                # Store relationships
                for rel in relationships:
                    # Convert properties dict to simple key-value pairs
                    simple_props = {}
                    for key, value in rel.properties.items():
                        if isinstance(value, (dict, list)):
                            simple_props[key] = json.dumps(value)
                        else:
                            simple_props[key] = str(value) if not isinstance(value, (str, int, float, bool)) else value
                    
                    session.run(
                        """
                        MATCH (from:Entity {entity_id: $from_id})
                        MATCH (to:Entity {entity_id: $to_id})
                        MERGE (from)-[r:RELATES_TO]->(to)
                        SET r.properties_text = $properties,
                            r.doc_id = $doc_id,
                            r.tenant = $tenant
                        """,
                        from_id=rel.from_entity,
                        to_id=rel.to_entity,
                        properties=json.dumps(simple_props),
                        doc_id=request.doc_id,
                        tenant=request.tenant
                    )
            finally:
                session.close()
            
            logger.info(
                "Graph extraction completed",
                doc_id=request.doc_id,
                entities=len(entities),
                relationships=len(relationships)
            )
            
            return GraphExtractionResponse(
                doc_id=request.doc_id,
                entities_count=len(entities),
                relationships_count=len(relationships),
                entities=entities,
                relationships=relationships
            )
    
    async def query_graph(
        self,
        request: GraphQueryRequest
    ) -> GraphQueryResponse:
        """Query the knowledge graph"""
        
        with tracer.start_as_current_span("query_graph") as span:
            span.set_attribute("query", request.query)
            span.set_attribute("tenant", request.tenant)
            
            results = []
            
            session = self.driver.session()
            try:
                # Simple pattern matching query
                result = session.run(
                    """
                    MATCH (e:Entity)
                    WHERE e.tenant = $tenant
                    AND toLower(e.label) CONTAINS toLower($query_param)
                    RETURN e
                    LIMIT $limit
                    """,
                    tenant=request.tenant,
                    query_param=request.query,
                    limit=request.max_results
                )
                
                for record in result:
                    results.append(dict(record芝["e"]))
            finally:
                session.close()
            
            return GraphQueryResponse(
                results=results,
                total=len(results)
            )


# Global service instance
settings = Settings()
kg_service = KnowledgeGraphService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Knowledge Graph",
    description="Knowledge graph service for entity and relationship extraction",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI
FastAPIInstrumentor.instrument_app(app)


@app.on_event("startup")
async def startup_event():
    """Initialize service"""
    await kg_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup"""
    await kg_service.close()


@app.post("/extract", response_model=GraphExtractionResponse)
async def extract_entities(request: GraphExtractionRequest):
    """Extract entities and relationships from text"""
    try:
        return await kg_service.extract_and_store(request)
    except Exception as e:
        logger.error("Entity extraction failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=GraphQueryResponse)
async def query_entities(request: GraphQueryRequest):
    """Query the knowledge graph"""
    try:
        return await kg_service.query_graph(request)
    except Exception as e:
        logger.error("Graph query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "service": "graph.kg"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics"""
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012)

