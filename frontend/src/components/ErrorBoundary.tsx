"use client";

import { AlertTriangle, RotateCcw, X } from "lucide-react";
import React from "react";

interface ErrorBoundaryProps {
  scope?: string;
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error(`[ErrorBoundary:${this.props.scope || "ui"}]`, error, info);
  }

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
        <div className="w-full max-w-md rounded-2xl border border-rose-800/70 bg-slate-950 p-5 shadow-2xl space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2 text-rose-300">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <h3 className="text-sm font-semibold">
                {this.props.scope ? `${this.props.scope} Error` : "Something went wrong"}
              </h3>
            </div>
            <button
              type="button"
              onClick={() => this.setState({ error: null })}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 cursor-pointer"
              aria-label="Close error modal"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <p className="text-xs text-slate-300 bg-slate-900 border border-slate-800 rounded-xl p-3 font-mono break-words">
            {this.state.error.message || "Unexpected client-side error"}
          </p>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => this.setState({ error: null })}
              className="inline-flex items-center gap-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-100 px-3 py-1.5 rounded-lg transition cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Retry
            </button>
          </div>
        </div>
      </div>
    );
  }
}
