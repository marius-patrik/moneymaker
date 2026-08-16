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
      className={`rounded-lg border px-4 py-3 text-sm shadow-sm min-w-[120px] text-center ${data.color || "bg-card border-border"}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-primary" />
      <div className="font-semibold text-foreground">{data.label}</div>
      {data.sub && <div className="text-xs text-muted-foreground mt-0.5">{data.sub}</div>}
      <Handle type="source" position={Position.Right} className="!bg-primary" />
    </div>
  );
}

const nodeTypes = { pipeline: PipelineNode };

function layoutDagre(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 40, ranksep: 60 });
  nodes.forEach((n) => g.setNode(n.id, { width: 140, height: 60 }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - 70, y: pos.y - 30 } };
  });
}

interface StrategyFlowProps {
  strategyName: string;
  params: Record<string, unknown>;
}

export function StrategyFlow({ strategyName, params }: StrategyFlowProps) {
  const paramSummary = Object.entries(params)
    .slice(0, 3)
    .map(([k, v]) => `${k}=${v}`)
    .join(", ");

  const rawNodes: Node[] = [
    {
      id: "data",
      type: "pipeline",
      position: { x: 0, y: 0 },
      data: { label: "DataProvider", sub: "yfinance / csv / alpaca", color: "bg-blue-50 border-blue-300 dark:bg-blue-950 dark:border-blue-800" },
    },
    {
      id: "strategy",
      type: "pipeline",
      position: { x: 0, y: 0 },
      data: { label: strategyName, sub: paramSummary || "default params", color: "bg-violet-50 border-violet-300 dark:bg-violet-950 dark:border-violet-700" },
    },
    {
      id: "risk",
      type: "pipeline",
      position: { x: 0, y: 0 },
      data: { label: "RiskManager", sub: "position sizing", color: "bg-amber-50 border-amber-300 dark:bg-amber-950 dark:border-amber-700" },
    },
    {
      id: "provider",
      type: "pipeline",
      position: { x: 0, y: 0 },
      data: { label: "ExecProvider", sub: "simulated / broker", color: "bg-emerald-50 border-emerald-300 dark:bg-emerald-950 dark:border-emerald-700" },
    },
    {
      id: "logger",
      type: "pipeline",
      position: { x: 0, y: 0 },
      data: { label: "TradeLogger", sub: "sessions/", color: "bg-rose-50 border-rose-300 dark:bg-rose-950 dark:border-rose-800" },
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
    <div className="h-32 overflow-hidden rounded-lg border sm:h-44">
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
