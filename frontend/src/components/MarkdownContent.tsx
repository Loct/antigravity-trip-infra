"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="text-sm text-slate-200 leading-relaxed space-y-2 break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className="text-base font-bold text-slate-100 mt-3 mb-1">{children}</h1>,
          h2: ({ children }) => <h2 className="text-sm font-bold text-slate-100 mt-3 mb-1">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-semibold text-slate-100 mt-2 mb-1">{children}</h3>,
          p: ({ children }) => <p className="leading-relaxed">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-5 space-y-1 text-slate-300">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1 text-slate-300">{children}</ol>,
          strong: ({ children }) => <strong className="font-semibold text-slate-100">{children}</strong>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer" className="text-sky-400 hover:text-sky-300 underline">
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="bg-slate-900 border border-slate-800 px-1.5 py-0.5 rounded text-xs text-sky-300">
              {children}
            </code>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-2 rounded-xl border border-slate-800">
              <table className="w-full text-xs text-left border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-900 text-slate-300">{children}</thead>,
          th: ({ children }) => <th className="px-3 py-2 font-semibold border-b border-slate-800">{children}</th>,
          td: ({ children }) => <td className="px-3 py-2 border-b border-slate-800/70 text-slate-300">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
