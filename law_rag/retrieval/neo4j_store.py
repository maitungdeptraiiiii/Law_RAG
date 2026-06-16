from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


def _env_enabled(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def graph_retrieval_enabled() -> bool:
    configured = os.getenv("GRAPH_RETRIEVAL_ENABLED")
    if configured is not None:
        return _env_enabled(configured, default=False)
    return _env_enabled(os.getenv("LAW_RAG_GRAPH_PIPELINE"), default=False)


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: str


def neo4j_config() -> Neo4jConfig:
    return Neo4jConfig(
        uri=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "lawrag-password"),
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )


class Neo4jLegalGraphStore:
    def __init__(self, config: Neo4jConfig | None = None) -> None:
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise RuntimeError("Missing dependency: install Neo4j driver with `pip install neo4j`.") from exc

        self.config = config or neo4j_config()
        connection_timeout = float(os.getenv("NEO4J_CONNECTION_TIMEOUT", "0.75"))
        self.driver = GraphDatabase.driver(
            self.config.uri,
            auth=(self.config.user, self.config.password),
            connection_timeout=connection_timeout,
            max_transaction_retry_time=float(os.getenv("NEO4J_MAX_TRANSACTION_RETRY_TIME", "0")),
        )

    def close(self) -> None:
        self.driver.close()

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def ensure_schema(self) -> None:
        statements = [
            "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.document_id IS UNIQUE",
            "CREATE CONSTRAINT article_id_unique IF NOT EXISTS FOR (a:Article) REQUIRE a.article_id IS UNIQUE",
            "CREATE CONSTRAINT legal_chunk_id_unique IF NOT EXISTS FOR (c:LegalChunk) REQUIRE c.chunk_id IS UNIQUE",
            "CREATE CONSTRAINT legal_issue_label_unique IF NOT EXISTS FOR (i:LegalIssue) REQUIRE i.label IS UNIQUE",
            "CREATE INDEX article_number_doc_number IF NOT EXISTS FOR (a:Article) ON (a.article_number, a.doc_number)",
            "CREATE INDEX article_document_title IF NOT EXISTS FOR (a:Article) ON (a.document_title)",
            "CREATE INDEX legal_chunk_article_clause IF NOT EXISTS FOR (c:LegalChunk) ON (c.article_number, c.clause_number)",
        ]
        with self.driver.session(database=self.config.database) as session:
            for statement in statements:
                session.execute_write(lambda tx, query=statement: tx.run(query).consume())

    def upsert_articles(self, articles: list[dict[str, Any]]) -> None:
        if not articles:
            return
        query = """
        UNWIND $rows AS row
        MERGE (d:Document {document_id: row.document_id})
        SET d.vbpl_id = row.vbpl_id,
            d.doc_number = row.doc_number,
            d.doc_type = row.doc_type,
            d.title = row.document_title,
            d.source_url = row.source_url,
            d.issue_date = row.issue_date
        MERGE (a:Article {article_id: row.article_id})
        SET a.vbpl_id = row.vbpl_id,
            a.doc_number = row.doc_number,
            a.doc_type = row.doc_type,
            a.document_title = row.document_title,
            a.article_number = row.article_number,
            a.article_title = row.article_title,
            a.chapter = row.chapter,
            a.section = row.section,
            a.source_file = row.source_file,
            a.source_url = row.source_url,
            a.issue_date = row.issue_date
        MERGE (d)-[:HAS_ARTICLE]->(a)
        WITH a, row
        MERGE (c:LegalChunk {chunk_id: row.chunk_id})
        SET c.parent_chunk_id = row.parent_chunk_id,
            c.vbpl_id = row.vbpl_id,
            c.doc_number = row.doc_number,
            c.doc_type = row.doc_type,
            c.document_title = row.document_title,
            c.article_id = row.article_id,
            c.article_number = row.article_number,
            c.article_title = row.article_title,
            c.clause_number = row.clause_number,
            c.point_number = row.point_number,
            c.part_index = row.part_index,
            c.part_count = row.part_count,
            c.subchunk_number = row.subchunk_number,
            c.subchunk_count = row.subchunk_count,
            c.fallback_split = row.fallback_split,
            c.display_title = row.display_title,
            c.chapter = row.chapter,
            c.section = row.section,
            c.source_file = row.source_file,
            c.source_url = row.source_url,
            c.issue_date = row.issue_date,
            c.text = row.text
        MERGE (a)-[:HAS_CHUNK]->(c)
        """
        with self.driver.session(database=self.config.database) as session:
            session.execute_write(lambda tx: tx.run(query, rows=articles).consume())

    def upsert_legal_issues(self, issues: list[dict[str, Any]]) -> None:
        if not issues:
            return
        query = """
        UNWIND $rows AS row
        MERGE (i:LegalIssue {label: row.label})
        SET i.issue_type = row.issue_type,
            i.confidence = row.confidence,
            i.retrieval_queries = row.retrieval_queries,
            i.semantic_queries = row.semantic_queries
        REMOVE i.queries
        WITH i, row
        UNWIND row.preferred_articles AS article_number
        MATCH (a:Article)
        WHERE a.article_number = article_number
          AND any(hint IN row.document_title_hints WHERE toLower(a.document_title) CONTAINS toLower(hint))
        MERGE (i)-[:PREFERRED_ARTICLE]->(a)
        WITH i, row
        UNWIND row.distinguish_from_articles AS article_number
        MATCH (a:Article)
        WHERE a.article_number = article_number
          AND any(hint IN row.document_title_hints WHERE toLower(a.document_title) CONTAINS toLower(hint))
        MERGE (i)-[:DISTINGUISH_FROM]->(a)
        """
        with self.driver.session(database=self.config.database) as session:
            session.execute_write(lambda tx: tx.run(query, rows=issues).consume())

    def upsert_references(self, references: list[dict[str, str]]) -> None:
        if not references:
            return
        query = """
        UNWIND $rows AS row
        MATCH (source:Article {article_id: row.source_article_id})
        MATCH (target:Article)
        WHERE target.article_number = row.target_article_number
          AND target.doc_number = source.doc_number
        MERGE (source)-[:REFERENCES]->(target)
        """
        with self.driver.session(database=self.config.database) as session:
            session.execute_write(lambda tx: tx.run(query, rows=references).consume())

    def issue_expansion(self, labels: list[str], *, limit: int = 8) -> list[dict[str, Any]]:
        labels = [label for label in labels if label]
        if not labels:
            return []
        query = """
        MATCH (i:LegalIssue)
        WHERE i.label IN $labels
        OPTIONAL MATCH (i)-[rel:PREFERRED_ARTICLE|DISTINGUISH_FROM]->(a:Article)
        OPTIONAL MATCH (a)-[:HAS_CHUNK]->(c:LegalChunk)
        WITH i, rel, a, c
        ORDER BY
          CASE type(rel) WHEN 'PREFERRED_ARTICLE' THEN 0 ELSE 1 END,
          CASE WHEN c.clause_number IS NULL THEN 1 ELSE 0 END,
          c.subchunk_number ASC,
          c.part_index ASC,
          c.chunk_id ASC
        RETURN i.label AS issue_label,
               type(rel) AS relation,
               a.article_id AS article_id,
               coalesce(c.chunk_id, a.chunk_id) AS chunk_id,
               a.document_title AS document_title,
               a.doc_number AS doc_number,
               a.article_number AS article_number,
               c.clause_number AS clause_number,
               c.point_number AS point_number,
               coalesce(c.source_file, a.source_file) AS source_file,
               coalesce(c.source_url, a.source_url) AS source_url,
               coalesce(c.text, a.text) AS text,
               i.retrieval_queries AS issue_queries,
               i.semantic_queries AS issue_semantic_queries
        LIMIT $limit
        """
        with self.driver.session(database=self.config.database) as session:
            rows = session.execute_read(
                lambda tx: [dict(record) for record in tx.run(query, labels=labels, limit=limit)]
            )
        return rows
