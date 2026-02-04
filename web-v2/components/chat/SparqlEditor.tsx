"use client";

import { useState, useEffect, useImperativeHandle, forwardRef, useRef } from "react";
import dynamic from "next/dynamic";

// Dynamically import Monaco editor to avoid SSR issues
const Editor = dynamic(() => import("@monaco-editor/react").then(mod => mod.Editor), {
    ssr: false,
    loading: () => (
        <div className="h-64 bg-slate-900 border border-slate-700 rounded-lg flex items-center justify-center">
            <p className="text-slate-400">Loading editor...</p>
        </div>
    ),
});

interface SparqlEditorProps {
    value: string;
    onChange?: (value: string) => void;
    onExecute?: () => void;
    readOnly?: boolean;
    height?: string;
    className?: string;
    autoFocus?: boolean;
}

export interface SparqlEditorRef {
    focus: () => void;
}

export const SparqlEditor = forwardRef<SparqlEditorRef, SparqlEditorProps>(({
    value,
    onChange,
    onExecute,
    readOnly = false,
    height = "400px",
    className = "",
    autoFocus = false,
}, ref) => {
    const [editorValue, setEditorValue] = useState(value);
    const editorInstanceRef = useRef<any>(null);

    useEffect(() => {
        setEditorValue(value);
    }, [value]);

    useImperativeHandle(ref, () => ({
        focus: () => {
            if (editorInstanceRef.current) {
                editorInstanceRef.current.focus();
            }
        },
    }));

    const handleEditorChange = (newValue: string | undefined) => {
        const updatedValue = newValue || "";
        setEditorValue(updatedValue);
        onChange?.(updatedValue);
    };

    const handleEditorDidMount = (editorInstance: any, monaco: any) => {
        editorInstanceRef.current = editorInstance;
        // Add key binding for Cmd/Ctrl + Enter
        if (onExecute && monaco) {
            editorInstance.addCommand(
                monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
                () => {
                    onExecute();
                }
            );
        }
        // Auto-focus if requested (use setTimeout to ensure editor is fully ready)
        if (autoFocus) {
            setTimeout(() => {
                editorInstance.focus();
            }, 0);
        }
    };

    return (
        <div className={`relative ${className}`}>
            <Editor
                height={height}
                language="sparql"
                value={editorValue}
                onChange={handleEditorChange}
                onMount={handleEditorDidMount}
                theme="vs-dark"
                options={{
                    readOnly,
                    minimap: { enabled: false },
                    fontSize: 14,
                    lineNumbers: "on",
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    tabSize: 2,
                    wordWrap: "on",
                    formatOnPaste: true,
                    formatOnType: false,
                    suggestOnTriggerCharacters: true,
                    quickSuggestions: true,
                    acceptSuggestionOnEnter: "on",
                    tabCompletion: "on",
                }}
            />
            {!readOnly && onExecute && (
                <div className="absolute bottom-2 right-2 text-xs text-slate-400">
                    Press Cmd/Ctrl + Enter to execute
                </div>
            )}
        </div>
    );
});

SparqlEditor.displayName = "SparqlEditor";

