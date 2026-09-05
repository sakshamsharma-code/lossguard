"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useParams } from "next/navigation";

type CaseEvidence = {
  return_id: string;
  user_id: string;
  return_rate_30d: number;
  return_rate_90d: number;
  avg_order_value: number;
  time_since_signup_days: number;
  shared_device_count: number;
  shared_address_count: number;
  shared_payment_method_count: number;
  cluster_info: {
    cluster_size: number;
    cluster_density: number;
    linked_user_ids: string[];
  };
  order_value: number;
  refund_amount: number;
  customer_lifetime_value: number;
  risk_score: number;
  expected_loss: number;
  decision_tier: string;
};

export default function CaseDetail() {
  const params = useParams();
  const returnId = params.id as string;

  const [evidence, setEvidence] = useState<CaseEvidence | null>(null);
  const [explanation, setExplanation] = useState<string>("");
  const [explaining, setExplaining] = useState(false);
  const [actionMsg, setActionMsg] = useState("");

  useEffect(() => {
    fetch(`http://localhost:8000/case/${returnId}`)
      .then((r) => r.json())
      .then(setEvidence)
      .catch(console.error);
  }, [returnId]);

  const getExplanation = () => {
    setExplaining(true);
    fetch(`http://localhost:8000/explain/${returnId}`, { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        setExplanation(data.summary);
        setExplaining(false);
      });
  };

  const takeAction = (action: string) => {
    fetch(`http://localhost:8000/decision/${returnId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    })
      .then((r) => r.json())
      .then(() => setActionMsg(`Logged: ${action}`));
  };

  if (!evidence) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
        <p className="text-zinc-500">Loading case...</p>
      </main>
    );
  }

  const riskPct = Math.round(evidence.risk_score * 100);

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8 max-w-4xl mx-auto">
      <a href="/dashboard" className="text-zinc-500 text-sm hover:text-zinc-300">
        ← Back to dashboard
      </a>

      <h1 className="text-2xl font-bold mt-4 mb-1 font-mono">{evidence.return_id}</h1>
      <p className="text-zinc-400 mb-8">User: {evidence.user_id}</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {/* Risk Gauge */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col items-center justify-center">
          <RiskGauge value={riskPct} />
          <p className="text-sm text-zinc-500 mt-2">Risk Score</p>
        </div>

        {/* Expected Loss */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col items-center justify-center">
          <motion.p
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="text-3xl font-bold text-red-400"
          >
            ₹{evidence.expected_loss.toLocaleString()}
          </motion.p>
          <p className="text-sm text-zinc-500 mt-2">Expected Loss</p>
          <p className="text-xs text-zinc-600 mt-1">
            (Risk {evidence.risk_score.toFixed(2)} × Refund ₹{evidence.refund_amount.toLocaleString()})
          </p>
        </div>

        {/* Decision Tier */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col items-center justify-center">
          <p className="text-xl font-bold uppercase tracking-wide">
            {evidence.decision_tier.replace("_", " ")}
          </p>
          <p className="text-sm text-zinc-500 mt-2">Recommended Action</p>
        </div>
      </div>

      {/* Evidence */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-8">
        <h2 className="font-semibold mb-4">Evidence</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <EvidenceRow label="30-day return rate" value={`${(evidence.return_rate_30d * 100).toFixed(0)}%`} />
          <EvidenceRow label="90-day return rate" value={`${(evidence.return_rate_90d * 100).toFixed(0)}%`} />
          <EvidenceRow label="Avg order value" value={`₹${evidence.avg_order_value.toLocaleString()}`} />
          <EvidenceRow label="Account age" value={`${evidence.time_since_signup_days} days`} />
          <EvidenceRow label="Shared devices" value={evidence.shared_device_count} highlight />
          <EvidenceRow label="Shared addresses" value={evidence.shared_address_count} highlight />
          <EvidenceRow label="Shared payment methods" value={evidence.shared_payment_method_count} highlight />
          <EvidenceRow label="Cluster size" value={evidence.cluster_info.cluster_size} highlight />
        </div>

        {evidence.cluster_info.linked_user_ids.length > 0 && (
          <div className="mt-4 pt-4 border-t border-zinc-800">
            <p className="text-xs text-zinc-500 mb-2">
              Linked accounts ({evidence.cluster_info.linked_user_ids.length}):
            </p>
            <div className="flex flex-wrap gap-2">
              {evidence.cluster_info.linked_user_ids.slice(0, 10).map((uid) => (
                <span key={uid} className="text-xs font-mono bg-zinc-800 px-2 py-1 rounded">
                  {uid}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* AI Explanation */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">AI Case Summary</h2>
          <button
            onClick={getExplanation}
            disabled={explaining}
            className="text-xs bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 rounded-lg"
          >
            {explaining ? "Generating..." : "Generate Summary"}
          </button>
        </div>
        {explanation && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-sm text-zinc-300 leading-relaxed"
          >
            {explanation}
          </motion.p>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={() => takeAction("approve")}
          className="flex-1 bg-green-600/20 border border-green-600/40 text-green-400 py-3 rounded-xl hover:bg-green-600/30"
        >
          Approve
        </button>
        <button
          onClick={() => takeAction("verify")}
          className="flex-1 bg-amber-600/20 border border-amber-600/40 text-amber-400 py-3 rounded-xl hover:bg-amber-600/30"
        >
          Request Verification
        </button>
        <button
          onClick={() => takeAction("reject")}
          className="flex-1 bg-red-600/20 border border-red-600/40 text-red-400 py-3 rounded-xl hover:bg-red-600/30"
        >
          Reject
        </button>
      </div>
      {actionMsg && <p className="text-sm text-zinc-500 mt-3">{actionMsg}</p>}
    </main>
  );
}

function EvidenceRow({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-zinc-500">{label}</span>
      <span className={highlight && Number(value) > 0 ? "text-amber-400 font-medium" : ""}>{value}</span>
    </div>
  );
}

function RiskGauge({ value }: { value: number }) {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  const color = value > 70 ? "#f87171" : value > 30 ? "#fbbf24" : "#4ade80";

  return (
    <svg width="120" height="120" viewBox="0 0 120 120">
      <circle cx="60" cy="60" r={radius} fill="none" stroke="#27272a" strokeWidth="10" />
      <motion.circle
        cx="60"
        cy="60"
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={circumference}
        initial={{ strokeDashoffset: circumference }}
        animate={{ strokeDashoffset: offset }}
        transition={{ duration: 1 }}
        transform="rotate(-90 60 60)"
      />
      <text x="60" y="68" textAnchor="middle" fontSize="24" fontWeight="bold" fill="white">
        {value}%
      </text>
    </svg>
  );
}
