import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { formatDate, indexingLabel, sourceHref } from "./api.ts";
import { AnswerPanel } from "./components/AnswerPanel.tsx";
import type { Message } from "./types.ts";

const abstain: Message = {
  id: "m1",
  role: "assistant",
  content: "No answer",
  mode: "abstain",
  retrieval_mode: "hybrid",
  contradictory: false,
  conflict_note: null,
  notice: null,
  dense_available: true,
  preamble: "No answer is shown.",
  abstention_reason: "below_threshold",
  citations: [],
  evidence: [],
  superseded: [],
  created_at: "2026-01-01T00:00:00Z",
};

describe("answer presentation", () => {
  it("shows an abstention without inventing a quote", () => {
    render(
      <MemoryRouter>
        <AnswerPanel message={abstain} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("abstain")).toHaveTextContent("No cited answer");
    expect(screen.queryByTestId("citation-link")).not.toBeInTheDocument();
  });

  it("links a citation to the cited revision", () => {
    const message: Message = {
      ...abstain,
      id: "m2",
      mode: "extractive",
      contradictory: true,
      conflict_note: "Both are quoted.",
      citations: [
        {
          id: "c1",
          chunk_id: "chunk-1",
          document_id: "doc-1",
          document_version_id: "ver-1",
          document_title: "Remote Work Policy",
          category: "company_policy",
          source_label: "Synthetic",
          revision: 2,
          section_title: "3. Location",
          page_number: 1,
          snippet: "Employees must work 2 in-office days per week.",
          snippet_sha256: "abc",
          effective_date: "2026-01-15",
          rank: 1,
          rrf_score: 0.03,
          bm25_score: 4.2,
          dense_score: 0.61,
        },
      ],
    };
    render(
      <MemoryRouter>
        <AnswerPanel message={message} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Sources disagree/)).toBeInTheDocument();
    expect(screen.getByTestId("citation-link")).toHaveAttribute(
      "href",
      sourceHref(message.citations[0]),
    );
    expect(indexingLabel("indexed_sparse")).toBe("Sparse only");
    expect(formatDate("2026-01-15")).toContain("2026");
  });
});
