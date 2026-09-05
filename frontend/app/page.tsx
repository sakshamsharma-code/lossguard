"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import Link from "next/link";

export default function Home() {
  const [expectedLoss, setExpectedLoss] = useState(0);

  useEffect(() => {
    fetch("http://localhost:8000/stats")
      .then((r) => r.json())
      .then((data) => {
        let start = 0;
        const end = data.total_expected_loss_today;
        const step = end / 40;
        const interval = setInterval(() => {
          start += step;
          if (start >= end) {
            setExpectedLoss(end);
            clearInterval(interval);
          } else {
            setExpectedLoss(Math.round(start));
          }
        }, 20);
      })
      .catch(console.error);
  }, []);

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col items-center justify-center p-8 text-center">
      <motion.h1
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-5xl font-bold mb-4"
      >
        Loss<span className="text-amber-400">Guard</span>
      </motion.h1>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="text-zinc-400 max-w-xl mb-8"
      >
        Not just "is this fraud?" — but "how much money is genuinely at risk,
        and where should limited review capacity go first?"
      </motion.p>

      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.5 }}
        className="bg-zinc-900 border border-zinc-800 rounded-2xl px-10 py-6 mb-10"
      >
        <p className="text-4xl font-bold text-red-400">₹{expectedLoss.toLocaleString()}</p>
        <p className="text-sm text-zinc-500 mt-1">potential loss flagged across current cases</p>
      </motion.div>

      <Link href="/dashboard">
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="bg-amber-500 text-zinc-950 font-semibold px-8 py-3 rounded-xl"
        >
          Open Command Center →
        </motion.button>
      </Link>
    </main>
  );
}
