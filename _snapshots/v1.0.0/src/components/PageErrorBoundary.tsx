"use client";

import { Component, ReactNode } from "react";
import Link from "next/link";

interface ErrorBoundaryState { hasError: boolean; error?: string }

export class PageErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-neutral-50">
          <div className="text-neutral-400">Sayfa yüklenemedi</div>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition"
          >
            Yeniden Dene
          </button>
          <Link href="/" className="text-blue-600 hover:underline text-sm">← Anasayfaya Dön</Link>
        </div>
      );
    }
    return this.props.children;
  }
}
