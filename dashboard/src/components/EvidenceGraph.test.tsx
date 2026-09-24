import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { EvidenceGraphResponse, GraphEdge, GraphNode } from "../types";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EvidenceGraph } from "./EvidenceGraph";

// ── Helpers ─────────────────────────────────────────────────────────────────────

function makeAsset(id: string, overrides: Partial<GraphNode> = {}): GraphNode {
  return {
    id,
    type: "asset",
    label: overrides.label ?? `Asset ${id}`,
    priority_score: overrides.priority_score ?? 75,
    priority_label: overrides.priority_label ?? "HIGH",
    quantum_vulnerable: overrides.quantum_vulnerable ?? false,
    confidence: overrides.confidence ?? 0.9,
    operation_anchor: overrides.operation_anchor ?? null,
    logical_asset_id: overrides.logical_asset_id,
    ...overrides,
  };
}

function makeEvidence(id: string, overrides: Partial<GraphNode> = {}): GraphNode {
  return {
    id,
    type: "evidence",
    label: overrides.label ?? `Evidence ${id}`,
    logical_asset_id: overrides.logical_asset_id,
    operation_anchor: overrides.operation_anchor,
    confidence: overrides.confidence,
    priority_score: overrides.priority_score,
    priority_label: overrides.priority_label,
    quantum_vulnerable: overrides.quantum_vulnerable,
    ...overrides,
  };
}

function makeEdge(source: string, target: string, overrides: Partial<GraphEdge> = {}): GraphEdge {
  return { source, target, relation: overrides.relation ?? "supports", ...overrides };
}

function makeData(nodes: GraphNode[], edges: GraphEdge[], scanId = 1): EvidenceGraphResponse {
  return { scan_id: scanId, nodes, edges };
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("EvidenceGraph", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. Empty data ───────────────────────────────────────────────────────────

  describe("empty data", () => {
    it("renders meaningful empty state with zero counts in toolbar", () => {
      render(<EvidenceGraph data={makeData([], [])} />);

      expect(screen.getByRole("img", { name: /Evidence graph with 0 nodes/ })).toBeInTheDocument();
      expect(screen.getByText("0 nodes, 0 edges")).toBeInTheDocument();
    });

    it("renders no SVG node groups when nodes and edges are empty", () => {
      render(<EvidenceGraph data={makeData([], [])} />);

      expect(document.querySelectorAll(".graph-node")).toHaveLength(0);
      expect(document.querySelectorAll(".graph-svg line")).toHaveLength(0);
    });

    it("renders the SVG defs (glow filter) even with no data", () => {
      render(<EvidenceGraph data={makeData([], [])} />);

      expect(document.querySelector("filter#glow")).toBeTruthy();
    });
  });

  // ── 2. Isolated nodes ───────────────────────────────────────────────────────

  describe("isolated nodes", () => {
    it("renders nodes with no edges as standalone circles", () => {
      const nodes = [
        makeAsset("a1", { label: "Asset 1" }),
        makeAsset("a2", { label: "Asset 2" }),
        makeEvidence("e1", { label: "Evidence 1" }),
      ];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const nodeGroups = document.querySelectorAll(".graph-node");
      expect(nodeGroups).toHaveLength(3);
    });

    it("uses one roving tab stop across isolated node buttons", () => {
      const nodes = [
        makeAsset("a1", { label: "Asset 1" }),
        makeEvidence("e1", { label: "Evidence 1" }),
      ];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const nodeGroups = document.querySelectorAll(".graph-node");
      expect(nodeGroups).toHaveLength(2);
      expect(nodeGroups[0]).toHaveAttribute("tabindex", "0");
      expect(nodeGroups[1]).toHaveAttribute("tabindex", "-1");
      nodeGroups.forEach((g) => expect(g).toHaveAttribute("role", "button"));
    });
  });

  // ── 3. Cycles ───────────────────────────────────────────────────────────────

  describe("cycles", () => {
    it("renders cyclic edges (A→B→C→A) without errors", () => {
      const nodes = [
        makeAsset("a", { label: "Node A" }),
        makeAsset("b", { label: "Node B" }),
        makeAsset("c", { label: "Node C" }),
      ];
      const edges = [makeEdge("a", "b"), makeEdge("b", "c"), makeEdge("c", "a")];

      expect(() => render(<EvidenceGraph data={makeData(nodes, edges)} />)).not.toThrow();

      expect(document.querySelectorAll(".graph-node")).toHaveLength(3);
      const svgLines = document.querySelectorAll(".graph-svg line");
      expect(svgLines.length).toBeGreaterThanOrEqual(3);
    });
  });

  // ── 4. Missing targets ─────────────────────────────────────────────────────

  describe("missing targets", () => {
    it("filters out edges referencing non-existent node IDs without crashing", () => {
      const nodes = [makeAsset("a1", { label: "Asset 1" }), makeAsset("a2", { label: "Asset 2" })];
      const edges = [
        makeEdge("a1", "a2"),
        makeEdge("a1", "nonexistent"),
        makeEdge("ghost", "a2"),
        makeEdge("phantom1", "phantom2"),
      ];

      expect(() => render(<EvidenceGraph data={makeData(nodes, edges)} />)).not.toThrow();

      // Only the valid a1→a2 edge should render
      const svgLines = document.querySelectorAll(".graph-svg line");
      expect(svgLines).toHaveLength(1);
    });

    it("renders correctly when all edges have missing targets", () => {
      const nodes = [makeAsset("a1", { label: "Only Node" })];
      const edges = [makeEdge("missing1", "missing2"), makeEdge("a1", "gone")];

      expect(() => render(<EvidenceGraph data={makeData(nodes, edges)} />)).not.toThrow();

      const svgLines = document.querySelectorAll(".graph-svg line");
      expect(svgLines).toHaveLength(0);
    });
  });

  // ── 5. Large datasets (>200 nodes) ─────────────────────────────────────────

  describe("large datasets", () => {
    it("caps rendering at maxNodes and shows 'Showing X of Y nodes' message", () => {
      const nodes: GraphNode[] = [];
      const edges: GraphEdge[] = [];

      for (let i = 0; i < 300; i++) {
        nodes.push(makeAsset(`large-${i}`, { label: `Node ${i}` }));
        if (i > 0) {
          edges.push(makeEdge(`large-${i - 1}`, `large-${i}`));
        }
      }

      render(<EvidenceGraph data={makeData(nodes, edges)} maxNodes={200} />);

      // isLarge is true when nodes.length > 50
      expect(
        screen.getByText("Showing 200 of 300 nodes. Use the filter to narrow results."),
      ).toBeInTheDocument();

      // Only 200 nodes should be rendered (capped)
      expect(document.querySelectorAll(".graph-node")).toHaveLength(200);
    });
  });

  // ── 6. Duplicate node IDs ───────────────────────────────────────────────────

  describe("duplicate node IDs", () => {
    it("renders duplicate node entries without crashing", () => {
      const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
      const nodes = [
        makeAsset("dup", { label: "First Duplicate" }),
        makeAsset("dup", { label: "Second Duplicate" }),
        makeAsset("unique", { label: "Unique" }),
      ];
      const edges = [makeEdge("dup", "unique")];

      expect(() => render(<EvidenceGraph data={makeData(nodes, edges)} />)).not.toThrow();

      // The component slices without explicit deduplication, so all 3 render
      expect(document.querySelectorAll(".graph-node")).toHaveLength(3);
      expect(consoleError.mock.calls.flat().join(" ")).not.toContain("same key");
      consoleError.mockRestore();
    });
  });

  // ── 7. Risk filtering ──────────────────────────────────────────────────────

  describe("risk filtering", () => {
    it("filters asset nodes by priority_label via the dropdown", async () => {
      const user = userEvent.setup();
      const nodes = [
        makeAsset("crit", { label: "Critical Asset", priority_label: "CRITICAL" }),
        makeAsset("high", { label: "High Asset", priority_label: "HIGH" }),
        makeAsset("low", { label: "Low Asset", priority_label: "LOW" }),
      ];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      // All 3 visible initially
      expect(document.querySelectorAll(".graph-node")).toHaveLength(3);
      expect(screen.getByText("3 nodes, 0 edges")).toBeInTheDocument();

      const select = screen.getByLabelText("Filter:");

      // Filter to CRITICAL
      await user.selectOptions(select, "CRITICAL");
      expect(document.querySelectorAll(".graph-node")).toHaveLength(1);
      expect(screen.getByText("1 node, 0 edges")).toBeInTheDocument();

      // Filter to HIGH
      await user.selectOptions(select, "HIGH");
      expect(document.querySelectorAll(".graph-node")).toHaveLength(1);

      // Filter to LOW
      await user.selectOptions(select, "LOW");
      expect(document.querySelectorAll(".graph-node")).toHaveLength(1);

      // Back to all
      await user.selectOptions(select, "all");
      expect(document.querySelectorAll(".graph-node")).toHaveLength(3);
      expect(screen.getByText("3 nodes, 0 edges")).toBeInTheDocument();
    });

    it("keeps evidence nodes visible regardless of risk filter selection", async () => {
      const user = userEvent.setup();
      const nodes = [
        makeAsset("a1", { label: "Asset", priority_label: "CRITICAL" }),
        makeEvidence("e1", { label: "Evidence Source" }),
      ];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const select = screen.getByLabelText("Filter:");
      await user.selectOptions(select, "LOW");

      // Only the evidence node should remain (no asset matches LOW)
      expect(document.querySelectorAll(".graph-node")).toHaveLength(1);
      expect(screen.getByText("1 node, 0 edges")).toBeInTheDocument();
    });

    it("populates the filter dropdown with unique sorted risk labels", () => {
      const nodes = [
        makeAsset("a1", { label: "Critical", priority_label: "CRITICAL" }),
        makeAsset("a2", { label: "High", priority_label: "HIGH" }),
        makeAsset("a3", { label: "Medium", priority_label: "MEDIUM" }),
        makeAsset("a4", { label: "Low", priority_label: "LOW" }),
      ];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const select = screen.getByLabelText("Filter:");
      const options = select.querySelectorAll("option");
      const values = Array.from(options).map((o) => o.value);

      expect(values).toEqual(["all", "CRITICAL", "HIGH", "LOW", "MEDIUM"]);
    });
  });

  // ── 8. Tooltip rendering ────────────────────────────────────────────────────

  describe("tooltip rendering", () => {
    it("shows tooltip with label, type badge, priority, quantum status, and confidence on hover", () => {
      const nodes = [
        makeAsset("a1", {
          label: "RSA Key",
          priority_label: "CRITICAL",
          priority_score: 95,
          quantum_vulnerable: true,
          confidence: 0.85,
          operation_anchor: "TLS-RSA",
        }),
      ];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const nodeEl = document.querySelector(".graph-node");
      expect(nodeEl).toBeTruthy();

      fireEvent.mouseEnter(nodeEl!);

      const tooltip = document.querySelector(".graph-tooltip");
      expect(tooltip).toBeTruthy();

      const tooltipQueries = within(tooltip as HTMLElement);
      expect(tooltipQueries.getByText("RSA Key")).toBeInTheDocument();
      expect(tooltipQueries.getByText("asset")).toBeInTheDocument();
      expect(tooltipQueries.getByText("Priority: CRITICAL (95/100)")).toBeInTheDocument();
      expect(tooltipQueries.getByText("Quantum vulnerable: Yes")).toBeInTheDocument();
      expect(tooltipQueries.getByText("Evidence confidence: 85%")).toBeInTheDocument();
      expect(tooltipQueries.getByText("Op: TLS-RSA")).toBeInTheDocument();
    });

    it("hides tooltip when the mouse leaves the node", () => {
      const nodes = [makeAsset("a1", { label: "Asset" })];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const nodeEl = document.querySelector(".graph-node");
      fireEvent.mouseEnter(nodeEl!);
      expect(document.querySelector(".graph-tooltip")).toBeTruthy();

      fireEvent.mouseLeave(nodeEl!);
      expect(document.querySelector(".graph-tooltip")).toBeNull();
    });

    it("shows minimal tooltip for evidence nodes without asset-specific fields", () => {
      const nodes = [makeEvidence("e1", { label: "Source File" })];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const nodeEl = document.querySelector(".graph-node");
      fireEvent.mouseEnter(nodeEl!);

      const tooltip = document.querySelector(".graph-tooltip");
      expect(tooltip).toBeTruthy();
      const tooltipQueries = within(tooltip as HTMLElement);
      expect(tooltipQueries.getByText("Source File")).toBeInTheDocument();
      expect(tooltipQueries.getByText("evidence")).toBeInTheDocument();
      // Asset-specific fields should NOT appear for evidence nodes
      expect(screen.queryByText(/Priority:/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Quantum vulnerable:/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Confidence:/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Op:/)).not.toBeInTheDocument();
    });

    it("handles asset with null priority_score gracefully in tooltip", () => {
      const nodes = [
        makeAsset("a1", { label: "Asset", priority_label: "HIGH", priority_score: null }),
      ];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const nodeEl = document.querySelector(".graph-node");
      fireEvent.mouseEnter(nodeEl!);

      // priority_score null should render as "—/100"
      expect(screen.getByText("Priority: HIGH (—/100)")).toBeInTheDocument();
    });
  });

  // ── 9. Mixed asset and evidence nodes ──────────────────────────────────────

  describe("mixed asset and evidence nodes", () => {
    it("does not use ambient randomness when laying out evidence nodes", () => {
      const random = vi.spyOn(Math, "random");
      const nodes = [makeAsset("a1"), makeEvidence("e1"), makeEvidence("e2")];

      render(<EvidenceGraph data={makeData(nodes, [makeEdge("a1", "e1")])} />);

      expect(random).not.toHaveBeenCalled();
    });

    it("renders both asset and evidence nodes with distinct visual styling", () => {
      const nodes = [
        makeAsset("a1", { label: "Asset" }),
        makeEvidence("e1", { label: "Evidence" }),
      ];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const nodeGroups = document.querySelectorAll(".graph-node");
      expect(nodeGroups).toHaveLength(2);

      const svg = document.querySelector(".graph-svg");
      expect(svg).toBeTruthy();

      // Asset main circle has the glow filter
      const assetGlow = svg?.querySelector('circle[filter="url(#glow)"]');
      expect(assetGlow).toBeTruthy();

      // Evidence inner ring (fill="none", stroke set, smaller radius)
      const innerRings = svg?.querySelectorAll('circle[fill="none"]');
      expect(innerRings?.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ── 10. Quantum vulnerable indicator ───────────────────────────────────────

  describe("quantum vulnerable indicator", () => {
    it("adds a red outer ring around quantum-vulnerable assets", () => {
      const nodes = [
        makeAsset("vuln", { label: "Vulnerable", quantum_vulnerable: true }),
        makeAsset("safe", { label: "Safe", quantum_vulnerable: false }),
      ];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const svg = document.querySelector(".graph-svg");

      // Quantum-vulnerable ring: r=10 (NODE_R+2), fill="none", stroke="#ef4444", strokeWidth=1.5
      const redRings = svg?.querySelectorAll('circle[stroke="#ef4444"][fill="none"]');
      expect(redRings?.length).toBeGreaterThanOrEqual(1);
    });

    it("does not render a red ring for non-vulnerable assets", () => {
      const nodes = [
        makeAsset("safe1", { label: "Safe 1", quantum_vulnerable: false }),
        makeAsset("safe2", { label: "Safe 2", quantum_vulnerable: false }),
      ];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const svg = document.querySelector(".graph-svg");

      // No red rings (stroke="#ef4444" only on quantum_vulnerable indicator)
      const redRings = svg?.querySelectorAll('circle[stroke="#ef4444"]');
      expect(redRings?.length).toBe(0);
    });
  });

  // ── 11. Node cap at 200 ─────────────────────────────────────────────────────

  describe("node cap at 200", () => {
    it("renders only 200 nodes when data contains 300 (default maxNodes)", () => {
      const nodes: GraphNode[] = [];
      for (let i = 0; i < 300; i++) {
        nodes.push(makeAsset(`cap-${i}`, { label: `Node ${i}` }));
      }

      render(<EvidenceGraph data={makeData(nodes, [])} />);

      // Default maxNodes is 200
      expect(document.querySelectorAll(".graph-node")).toHaveLength(200);
    });

    it("respects a custom maxNodes prop", () => {
      const nodes: GraphNode[] = [];
      for (let i = 0; i < 100; i++) {
        nodes.push(makeAsset(`custom-${i}`, { label: `Node ${i}` }));
      }

      render(<EvidenceGraph data={makeData(nodes, [])} maxNodes={50} />);

      expect(document.querySelectorAll(".graph-node")).toHaveLength(50);
    });
  });

  // ── 12. Edges filtered with nodes ──────────────────────────────────────────

  describe("edges filtered with nodes", () => {
    it("provides a semantic table row for every relationship", () => {
      const nodes = [
        makeAsset("asset-1", { label: "RSA key" }),
        makeEvidence("evidence-1", { label: "crypto.ts:12" }),
      ];
      const edges = [
        makeEdge("asset-1", "evidence-1", { relation: "supported_by" }),
        makeEdge("asset-1", "missing-node", { relation: "references" }),
      ];

      render(<EvidenceGraph data={makeData(nodes, edges)} />);

      const table = screen.getByRole("table", { name: "Evidence relationships" });
      const rows = within(table).getAllByRole("row");
      expect(rows).toHaveLength(3);
      expect(rows[1]).toHaveTextContent("RSA key");
      expect(rows[1]).toHaveTextContent("supported_by");
      expect(rows[1]).toHaveTextContent("crypto.ts:12");
      expect(rows[2]).toHaveTextContent("missing-node");
    });

    it("hides edges whose endpoint is filtered out by the risk filter", async () => {
      const user = userEvent.setup();
      const nodes = [
        makeAsset("crit", { label: "Critical", priority_label: "CRITICAL" }),
        makeAsset("high", { label: "High", priority_label: "HIGH" }),
        makeAsset("low", { label: "Low", priority_label: "LOW" }),
      ];
      const edges = [makeEdge("crit", "high"), makeEdge("high", "low"), makeEdge("low", "crit")];

      render(<EvidenceGraph data={makeData(nodes, edges)} />);

      // All 3 edges visible when filter is "all"
      let svgLines = document.querySelectorAll(".graph-svg line");
      expect(svgLines.length).toBeGreaterThanOrEqual(3);

      // Filter to CRITICAL only — no two visible nodes share an edge
      const select = screen.getByLabelText("Filter:");
      await user.selectOptions(select, "CRITICAL");
      svgLines = document.querySelectorAll(".graph-svg line");
      expect(svgLines).toHaveLength(0);

      // Filter to HIGH — same, single visible node
      await user.selectOptions(select, "HIGH");
      svgLines = document.querySelectorAll(".graph-svg line");
      expect(svgLines).toHaveLength(0);
    });

    it("shows edges only between visible nodes when two match the filter", async () => {
      const user = userEvent.setup();
      const nodes = [
        makeAsset("crit1", { label: "Critical 1", priority_label: "CRITICAL" }),
        makeAsset("crit2", { label: "Critical 2", priority_label: "CRITICAL" }),
        makeAsset("low1", { label: "Low 1", priority_label: "LOW" }),
      ];
      const edges = [
        makeEdge("crit1", "crit2"),
        makeEdge("crit1", "low1"),
        makeEdge("crit2", "low1"),
      ];

      render(<EvidenceGraph data={makeData(nodes, edges)} />);

      // Filter to CRITICAL: only the crit1↔crit2 edge should be visible
      const select = screen.getByLabelText("Filter:");
      await user.selectOptions(select, "CRITICAL");

      const svgLines = document.querySelectorAll(".graph-svg line");
      expect(svgLines).toHaveLength(1);
    });

    it("does not render edges pointing to non-existent nodes", () => {
      const nodes = [makeAsset("a1", { label: "A1" })];
      const edges = [
        makeEdge("a1", "missing"),
        makeEdge("missing", "a1"),
        makeEdge("gone1", "gone2"),
      ];

      render(<EvidenceGraph data={makeData(nodes, edges)} />);

      const svgLines = document.querySelectorAll(".graph-svg line");
      expect(svgLines).toHaveLength(0);
    });
  });

  // ── 13. Keyboard focus on nodes ────────────────────────────────────────────

  describe("keyboard focus on nodes", () => {
    it("uses the same selection action for click, Enter, and Space", () => {
      render(<EvidenceGraph data={makeData([makeAsset("a1", { label: "RSA node" })], [])} />);
      const node = screen.getByRole("button", { name: /RSA node/ });

      expect(node).toHaveAttribute("aria-pressed", "false");
      fireEvent.click(node);
      expect(node).toHaveAttribute("aria-pressed", "true");
      fireEvent.keyDown(node, { key: "Enter" });
      expect(node).toHaveAttribute("aria-pressed", "false");
      fireEvent.keyDown(node, { key: " " });
      expect(node).toHaveAttribute("aria-pressed", "true");
    });

    it("exposes node details to assistive technology when focused", () => {
      render(
        <EvidenceGraph
          data={makeData(
            [makeAsset("a1", { label: "Focused RSA", priority_label: "CRITICAL" })],
            [],
          )}
        />,
      );

      const node = screen.getByRole("button", { name: /Focused RSA/ });
      fireEvent.focus(node);

      const detail = screen.getByRole("status");
      expect(detail).toHaveTextContent("Focused RSA");
      expect(node).toHaveAttribute("aria-describedby", detail.id);
    });

    it("moves the roving tab stop with arrow keys", () => {
      const nodes = [
        makeAsset("a1", { label: "Asset" }),
        makeEvidence("e1", { label: "Evidence" }),
      ];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const nodeGroups = document.querySelectorAll(".graph-node");
      expect(nodeGroups).toHaveLength(2);

      expect(nodeGroups[0]).toHaveAttribute("tabindex", "0");
      expect(nodeGroups[1]).toHaveAttribute("tabindex", "-1");

      fireEvent.keyDown(nodeGroups[0], { key: "ArrowRight" });

      expect(nodeGroups[0]).toHaveAttribute("tabindex", "-1");
      expect(nodeGroups[1]).toHaveAttribute("tabindex", "0");
      expect(nodeGroups[1]).toHaveFocus();
    });

    it("includes the node type and priority_label in aria-label for asset nodes", () => {
      const nodes = [makeAsset("a1", { label: "MyAsset", priority_label: "CRITICAL" })];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const nodeGroup = document.querySelector(".graph-node");
      expect(nodeGroup?.getAttribute("aria-label")).toBe("asset: MyAsset, CRITICAL");
    });

    it("includes only the node type in aria-label for evidence nodes", () => {
      const nodes = [makeEvidence("e1", { label: "MyEvidence" })];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const nodeGroup = document.querySelector(".graph-node");
      expect(nodeGroup?.getAttribute("aria-label")).toBe("evidence: MyEvidence");
    });
  });

  // ── 14. Legend displays ─────────────────────────────────────────────────────

  describe("legend", () => {
    it("renders all four legend items", () => {
      render(<EvidenceGraph data={makeData([], [])} />);

      expect(screen.getByText("Asset node")).toBeInTheDocument();
      expect(screen.getByText("Evidence source")).toBeInTheDocument();
      expect(screen.getByText("Quantum-vulnerable")).toBeInTheDocument();
      expect(screen.getByText("Scroll to zoom, drag to pan")).toBeInTheDocument();
    });

    it("renders three colored legend dots", () => {
      render(<EvidenceGraph data={makeData([], [])} />);

      const legend = document.querySelector(".graph-legend");
      const dots = legend?.querySelectorAll(".legend-dot");
      expect(dots?.length).toBe(3);
    });
  });

  // ── Additional edge cases ───────────────────────────────────────────────────

  describe("edge cases", () => {
    it("handles asset nodes with null priority_label", () => {
      const nodes = [makeAsset("a1", { label: "No Label Asset", priority_label: null })];
      expect(() => render(<EvidenceGraph data={makeData(nodes, [])} />)).not.toThrow();
      expect(document.querySelectorAll(".graph-node")).toHaveLength(1);
    });

    it("handles asset nodes with null quantum_vulnerable", () => {
      const nodes = [makeAsset("a1", { label: "Asset", quantum_vulnerable: null })];
      expect(() => render(<EvidenceGraph data={makeData(nodes, [])} />)).not.toThrow();
      expect(document.querySelectorAll(".graph-node")).toHaveLength(1);
    });

    it("handles asset nodes with null confidence", () => {
      const nodes = [makeAsset("a1", { label: "Asset", confidence: null })];
      expect(() => render(<EvidenceGraph data={makeData(nodes, [])} />)).not.toThrow();
      expect(document.querySelectorAll(".graph-node")).toHaveLength(1);
    });

    it("handles empty string labels", () => {
      const nodes = [makeAsset("a1", { label: "" }), makeEvidence("e1", { label: "" })];
      expect(() => render(<EvidenceGraph data={makeData(nodes, [])} />)).not.toThrow();
      expect(document.querySelectorAll(".graph-node")).toHaveLength(2);
    });

    it("handles special characters in labels", () => {
      const nodes = [makeAsset("a1", { label: "RSA-OAEP & AES-GCM <test>" })];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      expect(screen.getByText("RSA-OAEP & AES-GCM <test>")).toBeInTheDocument();
    });

    it("renders SVG with correct accessibility attributes", () => {
      render(<EvidenceGraph data={makeData([makeAsset("a1")], [])} />);

      const svg = document.querySelector(".graph-svg");
      expect(svg).toHaveAttribute("viewBox", "0 0 800 600");
      expect(svg).toHaveAttribute("role", "img");
      expect(svg).toHaveAttribute("aria-label");

      const title = svg?.querySelector("title");
      expect(title?.textContent).toBe("Evidence dependency graph");

      const desc = svg?.querySelector("desc");
      expect(desc?.textContent).toBeTruthy();
      expect(desc?.textContent).toContain("cryptographic assets");
    });

    it("renders the glow filter definition in SVG defs", () => {
      render(<EvidenceGraph data={makeData([], [])} />);

      const defs = document.querySelector("defs");
      expect(defs).toBeTruthy();
      expect(defs?.querySelector("filter#glow")).toBeTruthy();
      expect(defs?.querySelector("feGaussianBlur")).toBeTruthy();
    });

    it("shows 'Showing X of Y nodes' message only when node count exceeds 50", () => {
      // 50 nodes — should NOT show the message
      const smallNodes: GraphNode[] = [];
      for (let i = 0; i < 50; i++) {
        smallNodes.push(makeAsset(`small-${i}`));
      }
      const { unmount } = render(<EvidenceGraph data={makeData(smallNodes, [])} />);
      expect(screen.queryByText(/Showing.*of.*nodes/)).not.toBeInTheDocument();
      unmount();

      // 51 nodes — should show the message
      const largeNodes: GraphNode[] = [];
      for (let i = 0; i < 51; i++) {
        largeNodes.push(makeAsset(`large-${i}`));
      }
      render(<EvidenceGraph data={makeData(largeNodes, [])} />);
      expect(
        screen.getByText("Showing 51 of 51 nodes. Use the filter to narrow results."),
      ).toBeInTheDocument();
    });

    it("renders evidence nodes with inner ring circle", () => {
      const nodes = [makeEvidence("e1", { label: "Evidence" })];
      render(<EvidenceGraph data={makeData(nodes, [])} />);

      const svg = document.querySelector(".graph-svg");

      // Evidence inner ring: r=5 (NODE_R-3), fill="none", strokeWidth=1.5
      const innerRing = svg?.querySelector('circle[r="5"][fill="none"]');
      expect(innerRing).toBeTruthy();
    });
  });
});
