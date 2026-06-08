"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { IngestResponse } from "@/lib/types";
import styles from "./UploadButton.module.css";

const MAX_FILE_BYTES = 25 * 1024 * 1024; // 25 MB — matches the server cap
const ACCEPTED_EXT = [".pdf", ".txt", ".md", ".markdown"];

/**
 * Neumorphic trigger button + drag-and-drop modal that POSTs to /ingest.
 *
 * After a successful upload it fires a `synapse:ingested` custom event so
 * any listener (currently the Header stats chips) can refetch /stats —
 * keeps this component decoupled from the rest of the app.
 */
export function UploadButton() {
  const [open, setOpen] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(incoming: FileList | File[]) {
    const next: File[] = [];
    const localSkips: string[] = [];
    for (const f of Array.from(incoming)) {
      const ext = "." + (f.name.split(".").pop() || "").toLowerCase();
      if (!ACCEPTED_EXT.includes(ext)) {
        localSkips.push(`${f.name} — unsupported (.${ext.slice(1)})`);
        continue;
      }
      if (f.size > MAX_FILE_BYTES) {
        localSkips.push(`${f.name} — too large (${formatSize(f.size)})`);
        continue;
      }
      next.push(f);
    }
    if (next.length) setFiles((prev) => [...prev, ...next]);
    if (localSkips.length) setError(localSkips.join("\n"));
    else setError(null);
  }

  function removeFile(idx: number) {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  async function upload() {
    if (files.length === 0 || uploading) return;
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.uploadFiles(files);
      setResult(res);
      setFiles([]);
      // Tell the rest of the app: corpus state just changed.
      window.dispatchEvent(new CustomEvent("synapse:ingested"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  function reset() {
    setFiles([]);
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  function close() {
    if (uploading) return;
    setOpen(false);
    // Defer reset so the modal contents don't visibly flicker during close fade.
    setTimeout(reset, 220);
  }

  // Esc closes the modal.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, uploading]);

  return (
    <>
      <button
        type="button"
        className={styles.trigger}
        onClick={() => setOpen(true)}
        aria-label="Add documents"
        title="Add documents"
      >
        <Plus />
      </button>

      {open && (
        <div className={styles.backdrop} onClick={close}>
          <div
            className={styles.modal}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Add documents"
          >
            <header className={styles.modalHeader}>
              <h2 className={styles.title}>Add documents</h2>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={close}
                disabled={uploading}
                aria-label="Close"
              >
                <Close />
              </button>
            </header>

            {!result ? (
              <>
                <div
                  className={`${styles.drop} ${dragActive ? styles.dropActive : ""}`}
                  onClick={() => inputRef.current?.click()}
                  onDragEnter={(e) => {
                    e.preventDefault();
                    setDragActive(true);
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragActive(true);
                  }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragActive(false);
                    addFiles(e.dataTransfer.files);
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <input
                    ref={inputRef}
                    type="file"
                    multiple
                    accept={ACCEPTED_EXT.join(",")}
                    style={{ display: "none" }}
                    onChange={(e) => {
                      if (e.target.files) addFiles(e.target.files);
                    }}
                  />
                  <div className={styles.dropInner}>
                    <div className={styles.dropIcon} aria-hidden>
                      <Plus large />
                    </div>
                    <p className={styles.dropTitle}>
                      {dragActive ? "Drop to upload" : "Drop files here or click to browse"}
                    </p>
                    <p className={styles.dropHint}>
                      .pdf · .txt · .md · up to 25 MB each
                    </p>
                  </div>
                </div>

                {files.length > 0 && (
                  <ul className={styles.fileList}>
                    {files.map((f, i) => (
                      <li key={`${f.name}-${i}`} className={styles.fileItem}>
                        <span className={styles.fileName} title={f.name}>{f.name}</span>
                        <span className={styles.fileSize}>{formatSize(f.size)}</span>
                        <button
                          type="button"
                          className={styles.removeFile}
                          onClick={() => removeFile(i)}
                          disabled={uploading}
                          aria-label={`Remove ${f.name}`}
                        >
                          <Close />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                {error && <p className={styles.error}>{error}</p>}

                <div className={styles.actions}>
                  <p className={styles.tip}>
                    New chunks are queryable immediately. To add them to the
                    knowledge graph too, run <code>app.graph.build</code>.
                  </p>
                  <button
                    type="button"
                    className={styles.uploadBtn}
                    onClick={upload}
                    disabled={uploading || files.length === 0}
                  >
                    {uploading
                      ? "Uploading…"
                      : `Upload ${files.length || ""} file${files.length === 1 ? "" : "s"}`.replace(
                          /\s{2,}/g,
                          " ",
                        ).trim()}
                  </button>
                </div>
              </>
            ) : (
              <div className={styles.result}>
                <p className={styles.resultHeadline}>
                  <span className={styles.checkmark} aria-hidden>✓</span>
                  Ingested <strong>{result.documents_ingested}</strong>{" "}
                  document{result.documents_ingested === 1 ? "" : "s"} —{" "}
                  <strong>{result.chunks_created}</strong>{" "}
                  chunk{result.chunks_created === 1 ? "" : "s"} added,{" "}
                  <strong>{result.chunks_embedded}</strong> embedded.
                </p>

                {result.accepted.length > 0 && (
                  <ul className={styles.acceptedList}>
                    {result.accepted.map((name) => (
                      <li key={name}>
                        <span className={styles.acceptedDot} aria-hidden />
                        {name}
                      </li>
                    ))}
                  </ul>
                )}

                {result.skipped.length > 0 && (
                  <details className={styles.skipped}>
                    <summary>{result.skipped.length} skipped</summary>
                    <ul>
                      {result.skipped.map((s, i) => (
                        <li key={i}>
                          <strong>{s.file}</strong> — {s.reason}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}

                <p className={styles.note}>{result.note}</p>

                <div className={styles.actions}>
                  <button
                    type="button"
                    className={styles.secondaryBtn}
                    onClick={reset}
                  >
                    Upload more
                  </button>
                  <button
                    type="button"
                    className={styles.uploadBtn}
                    onClick={close}
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function Plus({ large = false }: { large?: boolean }) {
  const s = large ? 30 : 18;
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={large ? 1.7 : 2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function Close() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  );
}
