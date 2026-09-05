"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";

type CaseSummary = {
  return_id: string;
  user_id: string;
  risk_score: number;
  expected_loss: number;
  decision_tier: string;
  refund_amount: number;
};

type Stats = {
  total_cases: number;
  high_risk_count: number;
  medium_risk_count: number;
  potential_rings: number;
  total_expected_loss_today: number;
};

const tierColor: Record<string, string> = {
  manual_review: "bg-red-500/20 text-red-400 border-red-500/40",
  verify: "bg-amber-500/20 text-amber-400 border-amber-500/40",
  auto_approve: "bg-green-500/20 text-green-400 border-green-500/40",
};

export default function Dashboard() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("http://localhost:8000/cases?limit=150").then((r) => r.json()),
      fetch("http://localhost:8000/stats").then((r) => r.json()),
    ])
      .then(([casesData, statsData]) => {
        setCases(casesData);
        setStats(statsData);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <motion.h1
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-3xl font-bold mb-1"
      >
        LossGuard — Command Center
      </motion.h1>
      <p className="text-zinc-400 mb-8">
        Cases sorted by <span className="text-amber-400 font-medium">expected loss</span>, not raw risk score.
      </p>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
          <StatCard label="Total Cases" value={stats.total_cases} />
          <StatCard label="Manual Review" value={stats.high_risk_count} accent="text-red-400" />
          <StatCard label="Needs Verify" value={stats.medium_risk_count} accent="text-amber-400" />
          <StatCard
            label="Total Expected Loss"
            value={`₹${stats.total_expected_loss_today.toLocaleString()}`}
            accent="text-red-400"
          />
        </div>
      )}

      {loading && <p className="text-zinc-500">Loading cases...</p>}

      <div className="space-y-3">
        {cases.map((c, i) => (
          <motion.div
            key={c.return_id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.02 }}
          >
            <Link href={`/case/${c.return_id}`}>
              <div className="flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-xl p-4 hover:border-zinc-600 transition-colors cursor-pointer">
                <div>
                  <p className="font-mono text-sm text-zinc-400">{c.return_id}</p>
                  <p className="text-sm text-zinc-500">User: {c.user_id}</p>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <p className="text-xs text-zinc-500">Risk</p>
                    <p className="font-semibold">{(c.risk_score * 100).toFixed(0)}%</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-zinc-500">Expected Loss</p>
                    <p className="font-semibold text-lg">₹{c.expected_loss.toLocaleString()}</p>
                  </div>
                  <span
                    className={`text-xs px-3 py-1 rounded-full border ${tierColor[c.decision_tier] || ""}`}
                  >
                    {c.decision_tier.replace("_", " ")}
                  </span>
                </div>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
    </main>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
      <p className="text-xs text-zinc-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${accent || ""}`}>{value}</p>
    </div>
  );
}
