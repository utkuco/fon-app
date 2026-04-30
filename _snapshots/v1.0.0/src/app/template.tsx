"use client";

import { motion } from "framer-motion";

export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <>
      {/* Navigation progress bar — replays on every navigation since template remounts */}
      <motion.div
        className="fixed top-0 left-0 right-0 z-[9999] h-0.5 bg-gradient-to-r from-blue-600 via-blue-400 to-blue-600"
        initial={{ scaleX: 0, opacity: 1 }}
        animate={{ scaleX: 1, opacity: 0 }}
        transition={{
          scaleX: { duration: 0.55, ease: [0.4, 0, 0.2, 1] },
          opacity: { duration: 0.25, delay: 0.45 },
        }}
        style={{ transformOrigin: "left" }}
      />

      {/* Page content — subtle slide-up fade-in */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: 0.35,
          ease: [0.4, 0, 0.2, 1],
        }}
      >
        {children}
      </motion.div>
    </>
  );
}
