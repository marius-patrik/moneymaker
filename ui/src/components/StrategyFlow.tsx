import { useCallback, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  Position,
  Handle,
} from "@xyflow/react";
import dagre from "dagre";
import "@xyflow/react/dist/style.css";

interface PipelineNodeProps {
  data: { label: string; sub?: string; color?: string };
}

function PipelineNode({ data }: PipelineNodeProps) {
  return (
    <div
      className={`w-[150px] rounded-xl border px-3 py-2.5 text-center text-sm ${data.color || "bg-card border-border"}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-primary" />
      <div className="truncate text-xs font-semibold text-foreground" title={data.label}>{data.label}</div>
      {data.sub && (
        <div className="truncate text-[10px] text-muted-foreground" title={data.sub}>{data.sub}</div>
      )}
      <Handle type="source" position={Position.Right} className="!bg-primary" />
    </div>
  );
}

const nodeTypes = { pipeline: PipelineNode };

function layoutDagre(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 28, ranksep: 44 });
  nodes.forEach((n) => g.setNode(n.id, { width: 150, height: 56 }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - 75, y: pos.y - 28 } };
  });
}

interface StrategyFlowProps {
  strategyName: string;
  params: Record<string, unknown>;
}

export function StrategyFlow({ strategyName, params }: StrategyFlowProps) {
  // Two params is all that fits legibly at node width.
  const paramSummary = Object.entries(params)
    .slice(0, 2)
    .map(([k, v]) => `${k}=${v}`)
    .join(" ");

  const rawNodes: Node[] = [
    {
      id: "data",
      type: "pipeline",
      position: { x: 0, y: 0 },
      data: { label: "DataProvider", sub: "yfinance / csv / alpaca", color: "bg-blue-50 border-blue-300 dark:bg-neutral-900 dark:border-blue-700" },
    },
    {
      id: "strategy",
      type: "pipeline",
      position: { x: 0, y: 0 },
      data: { label: strategyName, sub: paramSummary || "default params", color: "bg-violet-50 border-violet-300 dark:bg-neutral-900 dark:border-violet-600" },
    },
    {
      id: "risk",
      type: "pipeline",
      position: { x: 0, y: 0 },
      data: { label: "RiskManager", sub: "position sizing", color: "bg-amber-50 border-amber-300 dark:bg-neutral-900 dark:border-amber-600" },
    },
    {
      id: "provider",
      type: "pipeline",
      position: { x: 0, y: 0 },
      data: { label: "ExecProvider", sub: "simulated / broker", color: "bg-emerald-50 border-emerald-300 dark:bg-neutral-900 dark:border-emerald-600" },
    },
    {
      id: "logger",
      type: "pipeline",
      position: { x: 0, y: 0 },
      data: { label: "TradeLogger", sub: "sessions/", color: "bg-rose-50 border-rose-300 dark:bg-neutral-900 dark:border-rose-700" },
    },
  ];

  const rawEdges: Edge[] = [
    { id: "e1", source: "data", target: "strategy", animated: true },
    { id: "e2", source: "strategy", target: "risk", animated: true },
    { id: "e3", source: "risk", target: "provider", animated: true },
    { id: "e4", source: "provider", target: "logger", animated: true },
  ];

  const laidOut = layoutDagre(rawNodes, rawEdges);
  const [nodes, setNodes, onNodesChange] = useNodesState(laidOut);
  const [edges, , onEdgesChange] = useEdgesState(rawEdges);

  useEffect(() => {
    setNodes(layoutDagre(rawNodes, rawEdges));
  }, [strategyName]);

  return (
    <div className="h-28 overflow-hidden rounded-xl border bg-muted/20 sm:h-36">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={false}
        zoomOnScroll={false}
        panOnDrag={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} color="hsl(var(--border))" />
      </ReactFlow>
    </div>
  );
}
