"""API, versioning, retrieval, and security behavior."""

import hashlib
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from qdrant_client.models import PointStruct
from sqlalchemy import select

from app.config import sqlite_url
from app.demo_files import build_text_pdf
from app.main import create_app
from app.models import Chunk, DocumentVersion, IngestionJob
from app.reconcile import reconcile_index
from app.services.jobs import reap_stale_jobs
from app.services.vectors import list_point_ids
from tests.conftest import make_settings


def _upload(
    client: TestClient,
    filename: str,
    content: bytes,
    *,
    title: str,
    category: str = "company_policy",
    audience: str = "staff",
    effective_date: str = "2026-01-01",
    source_label: str = "Synthetic — test upload",
):
    return client.post(
        "/api/documents",
        files={"file": (filename, content, "application/octet-stream")},
        data={
            "title": title,
            "category": category,
            "source_label": source_label,
            "audience": audience,
            "effective_date": effective_date,
        },
    )


def _query(client: TestClient, question: str, **extra) -> dict:
    payload = {"question": question, **extra}
    response = client.post("/api/query", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_health_is_ok_and_ready_reports_hash_backend(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    ready = client.get("/ready")
    assert ready.status_code == 200
    body = ready.json()
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["qdrant"]["ok"] is True
    assert body["checks"]["embeddings"]["ok"] is True
    assert body["status"] == "ok"


def test_refuses_non_loopback_without_flag(tmp_path: Path) -> None:
    application = create_app(make_settings(tmp_path, api_host="0.0.0.0", allow_network_bind=False))
    try:
        with TestClient(application):
            raise AssertionError("public bind was accepted")
    except RuntimeError as exc:
        assert "non-loopback" in str(exc)


def test_network_bind_flag_allows_startup(tmp_path: Path) -> None:
    application = create_app(make_settings(tmp_path, api_host="0.0.0.0", allow_network_bind=True))
    with TestClient(application) as test_client:
        assert test_client.get("/health").status_code == 200


def test_rejects_bad_uploads(client: TestClient) -> None:
    rejected = _upload(client, "notes.exe", b"hello", title="Nope")
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "unsupported_extension"
    mismatch = _upload(client, "notes.pdf", b"this is not a pdf", title="Nope")
    assert mismatch.status_code == 400
    assert mismatch.json()["code"] == "mime_mismatch"
    empty = _upload(client, "notes.txt", b"", title="Nope")
    assert empty.status_code == 400
    assert empty.json()["code"] == "empty_file"


def test_seed_corpus_shapes_and_strips_html_script(seeded: TestClient) -> None:
    overview = seeded.get("/api/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert body["documents"] >= 5
    assert body["categories_in_use"] == 2
    assert body["chunks"] > 0
    assert body["demo"] is True
    documents = seeded.get("/api/documents").json()
    by_title = {item["title"]: item for item in documents}
    assert by_title["Remote Work Policy"]["original_filename"].endswith(".pdf")
    assert by_title["Remote Work Policy"]["current_revision"] == 2
    assert by_title["Remote Work Policy"]["policy_id"] == "POL-SEC-02"
    assert by_title["Leave and Holidays Policy"]["policy_id"] == "POL-SEC-01"
    assert by_title["Expense Reimbursement Policy"]["original_filename"].endswith(".docx")
    assert by_title["Onboarding Guide"]["original_filename"].endswith(".html")
    assert by_title["Notice Periods Orientation Briefing"]["category"] == "regulatory_briefing"
    assert by_title["Notice Periods Orientation Briefing"]["policy_id"] == "POL-SEC-07"
    versions = seeded.get(f"/api/documents/{by_title['Remote Work Policy']['id']}/versions").json()
    assert any(item["revision"] == 1 and item["is_current"] is False for item in versions)
    joined = []
    for document in documents:
        payload = seeded.get(
            f"/api/documents/{document['id']}/versions/{document['version_id']}"
        ).json()
        text = "\n".join(chunk["text"] for chunk in payload["chunks"])
        assert "SYNTHETIC" in text
        joined.append(text)
    everything = "\n".join(joined)
    assert "400 days" not in everything
    assert "Ignore all policies" not in everything
    assert "not a statute" in everything


def test_extractive_citation_is_exact_and_unanswerable_abstains(seeded: TestClient) -> None:
    leave = _query(seeded, "How many days of annual leave does a full-time employee receive?")
    assert leave["mode"] == "extractive"
    assert leave["retrieval_mode"] == "hybrid"
    assert any("25 days of annual leave" in item["snippet"] for item in leave["citations"])
    for citation in leave["citations"]:
        digest = hashlib.sha256(citation["snippet"].encode("utf-8")).hexdigest()
        assert citation["snippet_sha256"] == digest
        source = seeded.get(
            f"/api/documents/{citation['document_id']}/versions/{citation['document_version_id']}"
        ).json()
        chunks = {chunk["id"]: chunk["text"] for chunk in source["chunks"]}
        assert chunks[citation["chunk_id"]] == citation["snippet"]
    abstained = _query(seeded, "What is the sabbatical policy for pet iguanas?")
    assert abstained["mode"] == "abstain"
    assert abstained["citations"] == []
    assert abstained["abstention_reason"] == "below_threshold"


def test_abstention_on_out_of_scope_question(seeded: TestClient) -> None:
    """Out-of-corpus questions must abstain with telemetry and no citations."""
    body = _query(seeded, "What is the company pension matching formula for lunar mining staff?")
    assert body["mode"] == "abstain"
    assert body["citations"] == []
    assert body["abstention_reason"] == "below_threshold"
    assert body["evidence_thresholds"] is not None
    assert body["evidence_thresholds"]["min_overlap"] >= 1
    assert body["evidence_thresholds"]["min_bm25"] > 0
    assert "bm25_score" in body["evidence"][0] if body["evidence"] else True
    for row in body["evidence"]:
        assert "clears_abstention_gate" in row
        assert row["used"] is False


def test_superseded_version_is_not_cited(seeded: TestClient) -> None:
    """Current answers must cite only current revisions; superseded text stays out of evidence."""
    body = _query(seeded, "How many in-office days per week are required?")
    titles = {item["document_title"] for item in body["citations"]}
    assert "Remote Work Policy" in titles
    remote = [item for item in body["citations"] if item["document_title"] == "Remote Work Policy"]
    assert remote
    assert all(item["revision"] == 2 for item in remote)
    assert all("0 in-office days" not in item["snippet"] for item in remote)
    assert all(item["revision"] >= 1 for item in body["citations"])
    docs = seeded.get("/api/documents").json()
    remote_doc = next(item for item in docs if item["title"] == "Remote Work Policy")
    assert remote_doc["policy_id"] == "POL-SEC-02"
    versions = seeded.get(f"/api/documents/{remote_doc['id']}/versions").json()
    assert any(item["revision"] == 1 and item["is_current"] is False for item in versions)


@pytest.mark.parametrize("question", [
    "What did the previous version of the remote work policy require?",
    "How many office days did Remote Work Policy version 1 require?",
    "How many office days did version v1 of the remote work policy require?",
    "How many office days did the first version of the remote work policy require?",
    "What does revision 2 of the remote work policy say about office days?",
])
def test_version_scoped_questions_do_not_cite_current_as_historical(
    seeded: TestClient, question: str,
) -> None:
    body = _query(seeded, question)
    assert body["mode"] == "abstain"
    assert body["citations"] == []
    assert body["abstention_reason"] == "unsupported_version_scope"
    assert body["retrieval_telemetry"]["threshold_decision"] == "unsupported_version_scope"
    assert "version history" in body["content"]
    assert all(not row["used"] for row in body["evidence"])
    assert all(
        row["rejected_reason"] == "unsupported_version_scope"
        for row in body["evidence"] if row["clears_abstention_gate"]
    )


def test_citation_span_matches_chunk_sha(seeded: TestClient) -> None:
    """Citation snippet must equal the stored chunk text and match snippet_sha256."""
    body = _query(seeded, "How many days of annual leave does a full-time employee receive?")
    assert body["mode"] == "extractive"
    assert body["citations"]
    for citation in body["citations"]:
        digest = hashlib.sha256(citation["snippet"].encode("utf-8")).hexdigest()
        assert citation["snippet_sha256"] == digest
        source = seeded.get(
            f"/api/documents/{citation['document_id']}/versions/{citation['document_version_id']}"
        ).json()
        chunk = next(item for item in source["chunks"] if item["id"] == citation["chunk_id"])
        assert citation["snippet"] == chunk["text"]
        assert citation["snippet_sha256"] == chunk["text_sha256"]
        assert citation["snippet"] in chunk["text"]


def test_conflict_quotes_both_current_sources_and_hides_superseded(seeded: TestClient) -> None:
    body = _query(seeded, "How many in-office days per week are required?")
    titles = {item["document_title"] for item in body["citations"]}
    assert "Remote Work Policy" in titles
    assert "Field Role Remote Exception" in titles
    assert body["contradictory"] is True
    assert "2" in body["conflict_note"] and "0" in body["conflict_note"]
    remote = [item for item in body["citations"] if item["document_title"] == "Remote Work Policy"]
    assert remote
    assert all(item["revision"] == 2 for item in remote)
    assert all(
        "0 in-office days" not in item["snippet"] or item["document_title"] != "Remote Work Policy"
        for item in body["citations"]
    )
    assert any(
        item["snippet"].startswith("Employees must work 2") or "2 in-office days" in item["snippet"]
        for item in remote
    )
    assert body["evidence_thresholds"] is not None
    assert any(row["bm25_score"] > 0 or (row["dense_score"] or 0) > 0 for row in body["evidence"])


def test_citation_survives_replacement(seeded: TestClient) -> None:
    first = _query(seeded, "How many days of annual leave does a full-time employee receive?")
    original = next(
        item for item in first["citations"] if "25 days of annual leave" in item["snippet"]
    )
    conversation_id = first["conversation_id"]
    replacement = (
        "SYNTHETIC DOCUMENT — not a real policy and not legal advice.\n\n"
        "2. Annual leave\n"
        "A full-time employee receives 40 days of annual leave each calendar year.\n"
    )
    response = seeded.post(
        f"/api/documents/{original['document_id']}/versions",
        files={"file": ("leave-v2.txt", replacement.encode("utf-8"), "text/plain")},
        data={"effective_date": "2026-05-01", "title": "Leave and Holidays Policy"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["current_revision"] == 2
    reopened = seeded.get(f"/api/conversations/{conversation_id}")
    assert reopened.status_code == 200
    assistant = [item for item in reopened.json()["messages"] if item["role"] == "assistant"][0]
    kept = next(item for item in assistant["citations"] if item["id"] == original["id"])
    assert kept["snippet"] == original["snippet"]
    assert "25 days of annual leave" in kept["snippet"]
    assert kept["revision"] == 1
    assert kept["document_version_id"] == original["document_version_id"]
    assert kept["snippet_sha256"] == hashlib.sha256(kept["snippet"].encode("utf-8")).hexdigest()
    second = _query(seeded, "How many days of annual leave does a full-time employee receive?")
    assert any("40 days of annual leave" in item["snippet"] for item in second["citations"])
    assert all("25 days of annual leave" not in item["snippet"] for item in second["citations"])


def test_fault_injection_hides_superseded_vectors(tmp_path: Path) -> None:
    application = create_app(
        make_settings(tmp_path, fault_inject="after_commit_before_vector_delete")
    )
    with TestClient(application) as faulty:
        faulty.post("/api/demo/delete-all")
        first = _upload(
            faulty,
            "orange.txt",
            b"SYNTHETIC\n\n1. Shuttle\nThe ORANGE-SHUTTLE allowance is 11 shuttle days.\n",
            title="Shuttle Note",
        )
        assert first.status_code == 201, first.text
        found = _query(faulty, "What ORANGE-SHUTTLE allowance covers shuttle days?")
        assert found["mode"] == "extractive"
        old_chunk_id = found["citations"][0]["chunk_id"]
        replaced = faulty.post(
            f"/api/documents/{first.json()['id']}/versions",
            files={
                "file": (
                    "blue.txt",
                    b"SYNTHETIC\n\n1. Harbor\nThe BLUE-HARBOR allowance is 4 harbor days.\n",
                    "text/plain",
                )
            },
            data={"effective_date": "2026-04-01"},
        )
        assert replaced.status_code == 500
        assert replaced.json()["code"] == "fault_injected"
        points = list_point_ids(faulty.app.state.qdrant, faulty.app.state.settings)
        assert old_chunk_id in points
        session = faulty.app.state.session_factory()
        try:
            chunk = session.get(Chunk, old_chunk_id)
            assert chunk is not None
            assert chunk.is_current is False
        finally:
            session.close()
        hidden = _query(faulty, "What ORANGE-SHUTTLE allowance covers shuttle days?")
        assert all("ORANGE-SHUTTLE" not in item["snippet"] for item in hidden["citations"])
        visible = _query(faulty, "What BLUE-HARBOR allowance covers harbor days?")
        assert any("BLUE-HARBOR" in item["snippet"] for item in visible["citations"])


def test_two_instances_share_database_bm25(tmp_path: Path) -> None:
    database = tmp_path / "shared.sqlite3"
    first_app = create_app(
        make_settings(
            tmp_path / "a",
            database_url=sqlite_url(database),
            qdrant_path=str(tmp_path / "qdrant-a"),
            upload_dir=str(tmp_path / "uploads-a"),
        )
    )
    second_app = create_app(
        make_settings(
            tmp_path / "b",
            database_url=sqlite_url(database),
            qdrant_path=str(tmp_path / "qdrant-b"),
            upload_dir=str(tmp_path / "uploads-b"),
        )
    )
    with TestClient(first_app) as writer, TestClient(second_app) as reader:
        uploaded = _upload(
            writer,
            "beacon.txt",
            b"SYNTHETIC\n\n1. Beacon\nThe beacon color code is teal-harbor.\n",
            title="Beacon Note",
        )
        assert uploaded.status_code == 201, uploaded.text
        answer = _query(reader, "What is the beacon color code?")
        assert any("teal-harbor" in item["snippet"] for item in answer["citations"])
        assert (
            writer.get("/api/overview").json()["retrieval"]["corpus_version"]
            == (reader.get("/api/overview").json()["retrieval"]["corpus_version"])
        )


def test_audience_filter_is_applied(client: TestClient) -> None:
    uploaded = _upload(
        client,
        "bonus.txt",
        b"SYNTHETIC\n\n1. Bonus\nThe EXEC-BONUS-POOL percent is twelve for executives.\n",
        title="Executive Bonus Note",
        audience="exec",
    )
    assert uploaded.status_code == 201, uploaded.text
    staff = _query(client, "What percent is the EXEC-BONUS-POOL for executives?")
    assert staff["mode"] == "abstain"
    executive = _query(
        client,
        "What percent is the EXEC-BONUS-POOL for executives?",
        audience="exec",
    )
    assert any("EXEC-BONUS-POOL" in item["snippet"] for item in executive["citations"])


def test_sparse_fallback_when_qdrant_is_down(tmp_path: Path) -> None:
    application = create_app(
        make_settings(
            tmp_path,
            qdrant_mode="server",
            qdrant_url="http://127.0.0.1:9",
            qdrant_wait=False,
        )
    )
    with TestClient(application) as test_client:
        test_client.post("/api/demo/delete-all")
        uploaded = _upload(
            test_client,
            "leave.txt",
            b"SYNTHETIC\n\n2. Annual leave\nA full-time employee receives 25 days of annual leave.\n",
            title="Leave Note",
        )
        assert uploaded.status_code == 201, uploaded.text
        ready = test_client.get("/ready").json()
        assert ready["status"] == "degraded"
        assert ready["checks"]["qdrant"]["ok"] is False
        answer = _query(
            test_client, "How many days of annual leave does a full-time employee receive?"
        )
        assert answer["retrieval_mode"] == "sparse"
        assert answer["dense_available"] is False
        assert answer["notice"]
        assert any("25 days of annual leave" in item["snippet"] for item in answer["citations"])


def test_reaper_fails_stale_jobs(client: TestClient) -> None:
    uploaded = _upload(
        client,
        "note.txt",
        b"SYNTHETIC\n\n1. Note\nThe kettle color code is copper-lantern.\n",
        title="Kettle Note",
    )
    assert uploaded.status_code == 201, uploaded.text
    session = client.app.state.session_factory()
    try:
        version = session.scalar(select(DocumentVersion).limit(1))
        assert version is not None
        job = IngestionJob(
            id=str(uuid4()),
            document_version_id=version.id,
            status="RUNNING",
            heartbeat_at=datetime.now(UTC) - timedelta(hours=2),
            error=None,
            created_at=datetime.now(UTC) - timedelta(hours=2),
            started_at=datetime.now(UTC) - timedelta(hours=2),
            finished_at=None,
        )
        session.add(job)
        session.commit()
        job_id = job.id
        assert reap_stale_jobs(session, 60) == 1
        session.refresh(job)
        assert job.status == "FAILED"
        assert "stale heartbeat" in (job.error or "")
        assert job_id
    finally:
        session.close()


def test_hostile_uploads_fail_quickly(client: TestClient) -> None:
    pdf = _upload(
        client,
        "hostile.pdf",
        b"%PDF-1.4\n1 0 obj\n<<>>\nstream\nBI\n/W 1 /H 1 /BPC 8\nID\nxxxx\nendstream\nendobj\n",
        title="Hostile PDF",
    )
    assert pdf.status_code == 201, pdf.text
    assert pdf.json()["indexing_state"] == "failed"
    assert "unterminated inline image" in (pdf.json()["extraction_error"] or "")
    _assert_job_failed_quickly(client, pdf.json()["version_id"], "hostile_pdf")
    buffer = io_bytes_zip_bomb()
    docx = _upload(client, "bomb.docx", buffer, title="Hostile DOCX")
    assert docx.status_code == 201, docx.text
    assert docx.json()["indexing_state"] == "failed"
    assert "compression ratio" in (docx.json()["extraction_error"] or "")
    _assert_job_failed_quickly(client, docx.json()["version_id"], "docx_compression_ratio")


def test_duplicate_upload_and_delete(client: TestClient) -> None:
    content = b"SYNTHETIC\n\n1. Color\nThe banner color code is sea-glass.\n"
    first = _upload(client, "banner.txt", content, title="Banner Note")
    assert first.status_code == 201, first.text
    second = _upload(client, "banner-copy.txt", content, title="Banner Copy")
    assert second.status_code == 409
    assert second.json()["code"] == "duplicate_upload"
    removed = client.delete(f"/api/documents/{first.json()['id']}")
    assert removed.status_code == 204
    listed = client.get("/api/documents").json()
    assert listed == []
    hidden = _query(client, "What is the banner color code?")
    assert hidden["mode"] == "abstain"
    direct = client.get(f"/api/documents/{first.json()['id']}")
    assert direct.status_code == 200
    assert direct.json()["deleted"] is True


def test_reconcile_removes_stale_points_and_restores_missing(client: TestClient) -> None:
    uploaded = _upload(
        client,
        "restore.txt",
        b"SYNTHETIC\n\n1. Restore\nThe archive color code is moss-green.\n",
        title="Archive Note",
    )
    assert uploaded.status_code == 201, uploaded.text
    settings = client.app.state.settings
    qdrant = client.app.state.qdrant
    current = list_point_ids(qdrant, settings)
    assert current
    stale_id = str(uuid4())
    qdrant.upsert(
        collection_name=settings.qdrant_collection,
        points=[
            PointStruct(id=stale_id, vector=[0.01] * settings.embedding_dimensions, payload={})
        ],
        wait=True,
    )
    sample = next(iter(current))
    from app.services.vectors import delete_points

    delete_points(qdrant, settings, [sample])
    report = reconcile_index(client.app.state)
    assert report["deleted"] == 1
    assert report["embedded"] >= 1
    repaired = list_point_ids(qdrant, settings)
    assert stale_id not in repaired
    assert sample in repaired


def test_reconcile_is_idempotent(client: TestClient) -> None:
    uploaded = _upload(
        client,
        "idempotent.txt",
        b"SYNTHETIC\n\n1. Idem\nThe idempotent color code is slate-blue.\n",
        title="Idempotent Note",
    )
    assert uploaded.status_code == 201, uploaded.text
    first = reconcile_index(client.app.state)
    second = reconcile_index(client.app.state)
    assert first["error"] is None
    assert second["error"] is None
    assert second["deleted"] == 0
    assert second["embedded"] == 0
    assert second["current"] == first["current"]


def test_deleted_document_hidden_even_with_stale_vectors(client: TestClient) -> None:
    """Soft-delete must hide citations even if Qdrant still holds orphaned points."""
    content = b"SYNTHETIC\n\n1. Lantern\nThe lantern color code is amber-ridge.\n"
    uploaded = _upload(client, "lantern.txt", content, title="Lantern Note")
    assert uploaded.status_code == 201, uploaded.text
    found = _query(client, "What is the lantern color code?")
    assert any("amber-ridge" in item["snippet"] for item in found["citations"])
    chunk_id = found["citations"][0]["chunk_id"]
    doc_id = uploaded.json()["id"]
    removed = client.delete(f"/api/documents/{doc_id}")
    assert removed.status_code == 204
    # Re-inject the orphan vector to simulate a stale dense index after delete.
    settings = client.app.state.settings
    client.app.state.qdrant.upsert(
        collection_name=settings.qdrant_collection,
        points=[
            PointStruct(
                id=chunk_id,
                vector=[0.02] * settings.embedding_dimensions,
                payload={},
            )
        ],
        wait=True,
    )
    assert chunk_id in list_point_ids(client.app.state.qdrant, settings)
    hidden = _query(client, "What is the lantern color code?")
    assert hidden["mode"] == "abstain"
    assert hidden["citations"] == []
    telem = hidden["retrieval_telemetry"]
    assert telem is not None
    # Dense may surface the orphan; DB post-filter must reject it.
    if telem["dense_candidates"] > 0:
        assert telem["filter_rejected"] >= 1
        reasons = {item["reason"] for item in telem["filter_rejections"]}
        assert reasons & {
            "document_deleted",
            "chunk_not_current",
            "version_not_current",
        }
    repaired = reconcile_index(client.app.state)
    assert repaired["deleted"] >= 1
    assert chunk_id not in list_point_ids(client.app.state.qdrant, settings)


def test_retrieval_telemetry_exposes_fusion_and_latency(seeded: TestClient) -> None:
    body = _query(seeded, "How many days of annual leave does a full-time employee receive?")
    telem = body["retrieval_telemetry"]
    assert telem is not None
    assert telem["mode"] in {"hybrid", "sparse", "dense"}
    assert telem["embedding_backend"] in {"hash", "local"}
    assert telem["corpus_version"] >= 1
    assert telem["latency_ms"] >= 0
    assert telem["bm25_candidates"] >= 1
    assert telem["fused_candidates"] >= 1
    assert telem["threshold_decision"] == "cite"
    assert body["evidence"]
    row = body["evidence"][0]
    assert "bm25_rrf_contrib" in row
    assert "dense_rrf_contrib" in row
    assert row["rrf_score"] >= 0


def test_eval_questions_and_metrics(seeded: TestClient) -> None:
    from app.eval_metrics import evaluate_all, load_eval_rows

    rows = load_eval_rows()
    assert any(row["expect"] == "ambiguous" for row in rows)
    assert any(row["expect"] == "conflict" for row in rows)
    assert any(row["expect"] == "abstain" for row in rows)
    report = evaluate_all(seeded, rows, modes=("hybrid", "dense"))
    hybrid = report["modes"]["hybrid"]
    dense = report["modes"]["dense"]
    assert hybrid["recall_at_k"] == 1.0
    assert hybrid["mrr"] == 1.0
    assert hybrid["citation_precision"] == 1.0
    assert hybrid["citation_faithfulness"] == 1.0
    assert hybrid["abstention_accuracy"] == 1.0
    # Dense-only on the hash embedder may still recover gold titles via vectors.
    assert dense["recall_at_k"] >= 0.5
    assert dense["citation_faithfulness"] == 1.0
    assert dense["abstention_accuracy"] == 1.0


def test_heldout_dataset_is_separate_from_seed_fixture() -> None:
    from app.eval_metrics import HELDOUT_V1_PATH, load_eval_rows, resolve_eval_path

    seed = {row["question"] for row in load_eval_rows()}
    heldout_path = resolve_eval_path("heldout/v1")
    assert heldout_path == HELDOUT_V1_PATH
    heldout = load_eval_rows(heldout_path)
    assert len(heldout) >= 10
    categories = {row["category"] for row in heldout}
    assert {"exact", "paraphrase", "negation", "unanswerable", "superseded"} <= categories
    overlap = seed.intersection({row["question"] for row in heldout})
    assert not overlap, f"held-out questions must not duplicate seed fixture: {overlap}"


def test_overview_numbers_come_from_records(seeded: TestClient) -> None:
    body = seeded.get("/api/overview").json()
    documents = seeded.get("/api/documents").json()
    assert body["documents"] == len(documents)
    assert body["examples"]
    settings = seeded.get("/api/settings").json()
    assert settings["llm_mode"] == "extractive"
    assert settings["external_llm_calls"] is False
    assert settings["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"


def test_pdf_bytes_roundtrip_via_api(client: TestClient) -> None:
    content = build_text_pdf(
        "SYNTHETIC\n\n2. Annual leave\nA full-time employee receives 25 days of annual leave.\n"
    )
    uploaded = _upload(client, "leave.pdf", content, title="PDF Leave")
    assert uploaded.status_code == 201, uploaded.text
    answer = _query(client, "How many days of annual leave does a full-time employee receive?")
    assert any("25 days of annual leave" in item["snippet"] for item in answer["citations"])


def _assert_job_failed_quickly(client: TestClient, version_id: str, code: str) -> None:
    session = client.app.state.session_factory()
    try:
        job = session.scalar(
            select(IngestionJob)
            .where(IngestionJob.document_version_id == version_id)
            .order_by(IngestionJob.created_at.desc())
        )
        assert job is not None
        assert job.status == "FAILED"
        assert job.error == code
        assert job.started_at is not None and job.finished_at is not None
        elapsed = (job.finished_at - job.started_at).total_seconds()
        assert elapsed < 20
    finally:
        session.close()


def io_bytes_zip_bomb() -> bytes:
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "A" * 2_000_000)
    return buffer.getvalue()
