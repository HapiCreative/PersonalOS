/**
 * Phase 10: Export/Import UI.
 * Section 1.1: Core entities are exportable.
 * Section 1.7: User-owned data — always exportable.
 */

import { useState, useRef } from 'react';
import { tokens } from '../../styles/tokens';
import { adminApi } from '../../api/endpoints';
import type { ImportResponse } from '../../types';

export function ExportImportPanel() {
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(true);
  const [includeEnrichments, setIncludeEnrichments] = useState(true);
  const [mergeStrategy, setMergeStrategy] = useState<string>('skip_existing');
  const [exportResult, setExportResult] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleExport = async () => {
    setExporting(true);
    setError(null);
    setExportResult(null);
    try {
      const data = await adminApi.exportData({
        include_archived: includeArchived,
        include_enrichments: includeEnrichments,
      });

      // Trigger download
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `personalos_export_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);

      setExportResult(
        `Exported ${data.node_count} nodes, ${data.edge_count} edges, ${data.enrichment_count} enrichments.`
      );
    } catch (e: any) {
      setError(e.message || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  const handleImport = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError('Please select a JSON file to import.');
      return;
    }

    setImporting(true);
    setError(null);
    setImportResult(null);

    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const result = await adminApi.importData(data, mergeStrategy);
      setImportResult(result);
    } catch (e: any) {
      setError(e.message || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  return (
    <div style={styles.panel}>
      {/* Export Section */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Export Data</h3>
        <p style={styles.description}>
          Export all your Core entities (nodes, edges, enrichments) as a JSON file.
          This includes all node types and their companion data.
        </p>

        <div style={styles.optionRow}>
          <label style={styles.checkbox}>
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(e) => setIncludeArchived(e.target.checked)}
            />
            <span style={styles.checkboxLabel}>Include archived items</span>
          </label>
        </div>

        <div style={styles.optionRow}>
          <label style={styles.checkbox}>
            <input
              type="checkbox"
              checked={includeEnrichments}
              onChange={(e) => setIncludeEnrichments(e.target.checked)}
            />
            <span style={styles.checkboxLabel}>Include AI enrichments</span>
          </label>
        </div>

        <button
          onClick={handleExport}
          disabled={exporting}
          style={styles.primaryButton}
        >
          {exporting ? 'Exporting...' : 'Export to JSON'}
        </button>

        {exportResult && (
          <div style={styles.successMessage}>{exportResult}</div>
        )}
      </div>

      {/* Divider */}
      <div style={styles.divider} />

      {/* Import Section */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Import Data</h3>
        <p style={styles.description}>
          Import Core entities from a previously exported JSON file.
          Relationships between nodes will be preserved.
        </p>

        <div style={styles.optionRow}>
          <label style={styles.label}>Merge strategy:</label>
          <select
            value={mergeStrategy}
            onChange={(e) => setMergeStrategy(e.target.value)}
            style={styles.select}
          >
            <option value="skip_existing">Skip existing (match by title + type)</option>
            <option value="create_new">Create new (always create new nodes)</option>
          </select>
        </div>

        <div style={styles.optionRow}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            style={styles.fileInput}
          />
        </div>

        <button
          onClick={handleImport}
          disabled={importing}
          style={styles.secondaryButton}
        >
          {importing ? 'Importing...' : 'Import from JSON'}
        </button>

        {importResult && (
          <div style={styles.resultBox}>
            <div style={styles.resultTitle}>Import Complete</div>
            <div style={styles.resultRow}>
              <span>Nodes created:</span>
              <span style={styles.resultValue}>{importResult.nodes_created}</span>
            </div>
            <div style={styles.resultRow}>
              <span>Nodes skipped:</span>
              <span style={styles.resultValue}>{importResult.nodes_skipped}</span>
            </div>
            <div style={styles.resultRow}>
              <span>Edges created:</span>
              <span style={styles.resultValue}>{importResult.edges_created}</span>
            </div>
            <div style={styles.resultRow}>
              <span>Edges skipped:</span>
              <span style={styles.resultValue}>{importResult.edges_skipped}</span>
            </div>
            <div style={styles.resultRow}>
              <span>Enrichments created:</span>
              <span style={styles.resultValue}>{importResult.enrichments_created}</span>
            </div>
            {importResult.errors.length > 0 && (
              <div style={styles.errorList}>
                <div style={styles.errorTitle}>Errors ({importResult.errors.length}):</div>
                {importResult.errors.map((err, i) => (
                  <div key={i} style={styles.errorItem}>{err}</div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Global error */}
      {error && <div style={styles.errorMessage}>{error}</div>}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {},
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 16,
    color: tokens.colors.text,
    marginBottom: 8,
  },
  description: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    lineHeight: 1.5,
    marginBottom: 16,
  },
  optionRow: {
    marginBottom: 12,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  checkbox: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    cursor: 'pointer',
  },
  checkboxLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
  },
  label: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    minWidth: 120,
  },
  select: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    padding: '6px 10px',
    cursor: 'pointer',
  },
  fileInput: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
  },
  primaryButton: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: 'none',
    background: tokens.colors.accent,
    color: tokens.colors.background,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 8,
  },
  secondaryButton: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
    marginTop: 8,
  },
  divider: {
    borderTop: `1px solid ${tokens.colors.border}`,
    marginBottom: 24,
  },
  successMessage: {
    marginTop: 12,
    padding: '8px 12px',
    background: `${tokens.colors.success}15`,
    border: `1px solid ${tokens.colors.success}30`,
    borderRadius: tokens.radius,
    color: tokens.colors.success,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
  },
  errorMessage: {
    marginTop: 12,
    padding: '8px 12px',
    background: `${tokens.colors.error}15`,
    border: `1px solid ${tokens.colors.error}30`,
    borderRadius: tokens.radius,
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
  },
  resultBox: {
    marginTop: 12,
    padding: 16,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
  },
  resultTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 14,
    color: tokens.colors.success,
    marginBottom: 12,
  },
  resultRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    padding: '4px 0',
  },
  resultValue: {
    fontFamily: tokens.fonts.mono,
    color: tokens.colors.accent,
  },
  errorList: {
    marginTop: 12,
    borderTop: `1px solid ${tokens.colors.border}`,
    paddingTop: 8,
  },
  errorTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 600,
    color: tokens.colors.error,
    marginBottom: 4,
  },
  errorItem: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.error,
    padding: '2px 0',
  },
};
