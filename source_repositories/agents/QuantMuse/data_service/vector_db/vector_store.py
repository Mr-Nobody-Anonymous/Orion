import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime
import json
import pickle
from pathlib import Path
import sqlite3
from dataclasses import dataclass

@dataclass
class VectorDocument:
    """Vector document data structure"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: np.ndarray
    timestamp: datetime
    source: str

class VectorStore:
    """Vector database store for trading system documents"""
    
    def __init__(self, db_path: str = "vector_store.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._init_database()
        
    def _init_database(self):
        """Initialize vector database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self._create_tables()
            self.logger.info("Vector database initialized")
        except Exception as e:
            self.logger.error(f"Error initializing vector database: {e}")
    
    def _create_tables(self):
        """Create necessary database tables"""
        cursor = self.conn.cursor()
        
        # Documents table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                metadata TEXT,
                source TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Embeddings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS embeddings (
                id TEXT PRIMARY KEY,
                embedding_data BLOB,
                dimension INTEGER,
                FOREIGN KEY (id) REFERENCES documents (id)
            )
        ''')
        
        # Collections table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collections (
                name TEXT PRIMARY KEY,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Document collections mapping
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_collections (
                document_id TEXT,
                collection_name TEXT,
                FOREIGN KEY (document_id) REFERENCES documents (id),
                FOREIGN KEY (collection_name) REFERENCES collections (name),
                PRIMARY KEY (document_id, collection_name)
            )
        ''')
        
        self.conn.commit()
    
    def add_document(self, document: VectorDocument, 
                    collection: str = "default") -> bool:
        """Add document to vector store"""
        try:
            cursor = self.conn.cursor()
            
            # Insert document
            cursor.execute('''
                INSERT OR REPLACE INTO documents (id, content, metadata, source, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                document.id,
                document.content,
                json.dumps(document.metadata),
                document.source,
                document.timestamp.isoformat()
            ))
            
            # Insert embedding
            embedding_bytes = pickle.dumps(document.embedding)
            cursor.execute('''
                INSERT OR REPLACE INTO embeddings (id, embedding_data, dimension)
                VALUES (?, ?, ?)
            ''', (
                document.id,
                embedding_bytes,
                len(document.embedding)
            ))
            
            # Add to collection
            cursor.execute('''
                INSERT OR IGNORE INTO collections (name) VALUES (?)
            ''', (collection,))
            
            cursor.execute('''
                INSERT OR IGNORE INTO document_collections (document_id, collection_name)
                VALUES (?, ?)
            ''', (document.id, collection))
            
            self.conn.commit()
            self.logger.info(f"Document {document.id} added to collection {collection}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding document: {e}")
            return False
    
    def get_document(self, document_id: str) -> Optional[VectorDocument]:
        """Get document by ID"""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute('''
                SELECT d.id, d.content, d.metadata, d.source, d.timestamp, e.embedding_data
                FROM documents d
                JOIN embeddings e ON d.id = e.id
                WHERE d.id = ?
            ''', (document_id,))
            
            row = cursor.fetchone()
            if row:
                return VectorDocument(
                    id=row[0],
                    content=row[1],
                    metadata=json.loads(row[2]) if row[2] else {},
                    source=row[3],
                    timestamp=datetime.fromisoformat(row[4]),
                    embedding=pickle.loads(row[5])
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting document: {e}")
            return None
    
    def search_similar(self, query_embedding: np.ndarray, 
                      collection: str = "default",
                      top_k: int = 10,
                      similarity_threshold: float = 0.5) -> List[Tuple[VectorDocument, float]]:
        """Search for similar documents"""
        try:
            cursor = self.conn.cursor()
            
            # Get all documents in collection
            cursor.execute('''
                SELECT d.id, d.content, d.metadata, d.source, d.timestamp, e.embedding_data
                FROM documents d
                JOIN embeddings e ON d.id = e.id
                JOIN document_collections dc ON d.id = dc.document_id
                WHERE dc.collection_name = ?
            ''', (collection,))
            
            results = []
            for row in cursor.fetchall():
                document = VectorDocument(
                    id=row[0],
                    content=row[1],
                    metadata=json.loads(row[2]) if row[2] else {},
                    source=row[3],
                    timestamp=datetime.fromisoformat(row[4]),
                    embedding=pickle.loads(row[5])
                )
                
                # Calculate similarity
                similarity = self._calculate_similarity(query_embedding, document.embedding)
                
                if similarity >= similarity_threshold:
                    results.append((document, similarity))
            
            # Sort by similarity and return top_k
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
            
        except Exception as e:
            self.logger.error(f"Error searching documents: {e}")
            return []
    
    def _calculate_similarity(self, embedding1: np.ndarray, 
                            embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between embeddings"""
        try:
            # Normalize embeddings
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # Calculate cosine similarity
            similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            self.logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def delete_document(self, document_id: str) -> bool:
        """Delete document from vector store"""
        try:
            cursor = self.conn.cursor()
            
            # Delete from document_collections
            cursor.execute('DELETE FROM document_collections WHERE document_id = ?', (document_id,))
            
            # Delete embedding
            cursor.execute('DELETE FROM embeddings WHERE id = ?', (document_id,))
            
            # Delete document
            cursor.execute('DELETE FROM documents WHERE id = ?', (document_id,))
            
            self.conn.commit()
            self.logger.info(f"Document {document_id} deleted")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting document: {e}")
            return False
    
    def get_collection_stats(self, collection: str = "default") -> Dict[str, Any]:
        """Get statistics for a collection"""
        try:
            cursor = self.conn.cursor()
            
            # Count documents
            cursor.execute('''
                SELECT COUNT(*) FROM document_collections WHERE collection_name = ?
            ''', (collection,))
            doc_count = cursor.fetchone()[0]
            
            # Get embedding dimensions
            cursor.execute('''
                SELECT e.dimension FROM embeddings e
                JOIN document_collections dc ON e.id = dc.document_id
                WHERE dc.collection_name = ?
                LIMIT 1
            ''', (collection,))
            dimension_row = cursor.fetchone()
            dimension = dimension_row[0] if dimension_row else 0
            
            # Get sources
            cursor.execute('''
                SELECT DISTINCT d.source FROM documents d
                JOIN document_collections dc ON d.id = dc.document_id
                WHERE dc.collection_name = ?
            ''', (collection,))
            sources = [row[0] for row in cursor.fetchall()]
            
            return {
                'collection': collection,
                'document_count': doc_count,
                'embedding_dimension': dimension,
                'sources': sources
            }
            
        except Exception as e:
            self.logger.error(f"Error getting collection stats: {e}")
            return {}
    
    def list_collections(self) -> List[str]:
        """List all collections"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT name FROM collections')
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Error listing collections: {e}")
            return []
    
    def create_collection(self, name: str, description: str = "") -> bool:
        """Create a new collection"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO collections (name, description)
                VALUES (?, ?)
            ''', (name, description))
            self.conn.commit()
            
            self.logger.info(f"Collection {name} created")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating collection: {e}")
            return False
    
    def delete_collection(self, name: str) -> bool:
        """Delete a collection and all its documents"""
        try:
            cursor = self.conn.cursor()
            
            # Get all documents in collection
            cursor.execute('''
                SELECT document_id FROM document_collections WHERE collection_name = ?
            ''', (name,))
            document_ids = [row[0] for row in cursor.fetchall()]
            
            # Delete all documents in collection
            for doc_id in document_ids:
                self.delete_document(doc_id)
            
            # Delete collection
            cursor.execute('DELETE FROM collections WHERE name = ?', (name,))
            self.conn.commit()
            
            self.logger.info(f"Collection {name} deleted")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting collection: {e}")
            return False
    
    def export_collection(self, collection: str, filepath: str) -> bool:
        """Export collection to file"""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute('''
                SELECT d.id, d.content, d.metadata, d.source, d.timestamp, e.embedding_data
                FROM documents d
                JOIN embeddings e ON d.id = e.id
                JOIN document_collections dc ON d.id = dc.document_id
                WHERE dc.collection_name = ?
            ''', (collection,))
            
            documents = []
            for row in cursor.fetchall():
                documents.append({
                    'id': row[0],
                    'content': row[1],
                    'metadata': json.loads(row[2]) if row[2] else {},
                    'source': row[3],
                    'timestamp': row[4],
                    'embedding': pickle.loads(row[5]).tolist()
                })
            
            with open(filepath, 'w') as f:
                json.dump(documents, f, indent=2)
            
            self.logger.info(f"Collection {collection} exported to {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting collection: {e}")
            return False
    
    def close(self):
        """Close database connection"""
        if hasattr(self, 'conn'):
            self.conn.close() 