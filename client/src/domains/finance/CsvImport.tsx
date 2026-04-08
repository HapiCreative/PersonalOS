/**
 * Finance: CSV Import UI.
 * File upload -> column mapping -> preview -> confirm.
 * Section F1.5.2.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { tokens } from '../../styles/tokens';
import { financeAccountsApi, financeCsvApi } from '../../api/endpoints';
import type { AccountResponse, CsvPreviewResponse, CsvImportResult } from '../../types';

// Internal fields that need to be mapped to CSV columns
const MAPPABLE_FIELDS = [
  { key: 'date', label: 'Date', required: true },
  { key: 'amount', label: 'Amount', required: true },
  { key: 'description', label: 'Description', required: false },
  { key: 'counterparty', label: 'Counterparty', required: false },
  { key: 'category', label: 'Category', required: false },
  { key: 'external_id', label: 'External ID', required: false },
  { key: 'balance', label: 'Balance', required: false },
  { key: 'transaction_type', label: 'Type', required: false },
];

type ImportStep = 'upload' | 'mapping' | 'preview' | 'result';

interface CsvImportProps {
  onClose: () => void;
  onImported: () => void;
}

export function CsvImport({ onClose, onImported }: CsvImportProps) {
  const [step, setStep] = useState<ImportStep>('upload');
  const [accounts, setAccounts] = useState<AccountResponse[]>([]);
  const [accountId, setAccountId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<CsvPreviewResponse | null>(null);
  const [result, setResult] = useState<CsvImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    financeAccountsApi.list({ is_active: true, limit: 100 })
      .then((res) => {
        setAccounts(res.items);
        if (res.items.length > 0) setAccountId(res.items[0].node_id);
      })
      .catch(() => {});
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    setFile(selected);
    setError(null);

    // Read first line to detect columns
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      const firstLine = text.split('\n')[0];
      const headers = firstLine.split(',').map((h) => h.trim().replace(/"/g, ''));
      setCsvHeaders(headers);

      // Auto-map common column names
      const autoMapping: Record<string, string> = {};
      for (const field of MAPPABLE_FIELDS) {
        const match = headers.find((h) =>
          h.toLowerCase().includes(field.key) ||
          (field.key === 'date' && h.toLowerCase().includes('date')) ||
          (field.key === 'amount' && h.toLowerCase().includes('amount')) ||
          (field.key === 'description' && (h.toLowerCase().includes('desc') || h.toLowerCase().includes('memo'))) ||
          (field.key === 'counterparty' && (h.toLowerCase().includes('merchant') || h.toLowerCase().includes('payee')))
        );
        if (match) autoMapping[field.key] = match;
      }
      setMapping(autoMapping);
      setStep('mapping');
    };
    reader.readAsText(selected);
  }, []);

  const handlePreview = useCallback(async () => {
    if (!file || !accountId) return;
    if (!mapping.date || !mapping.amount) {
      setError('Date and Amount columns are required');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await financeCsvApi.previewWithMapping(accountId, file, mapping);
      setPreview(res);
      setStep('preview');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [file, accountId, mapping]);

  const handleImport = useCallback(async () => {
    if (!file || !accountId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await financeCsvApi.executeWithMapping(accountId, file, mapping, 'default');
      setResult(res);
      setStep('result');
      onImported();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [file, accountId, mapping, onImported]);

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={styles.heading}>CSV Import</h2>
        <button style={styles.closeButton} onClick={onClose}>Back</button>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Step indicators */}
      <div style={styles.steps}>
        {(['upload', 'mapping', 'preview', 'result'] as ImportStep[]).map((s, i) => (
          <span
            key={s}
            style={{
              ...styles.stepLabel,
              color: step === s ? tokens.colors.accent : tokens.colors.textMuted,
              fontWeight: step === s ? 600 : 400,
            }}
          >
            {i + 1}. {s === 'upload' ? 'Upload' : s === 'mapping' ? 'Map Columns' : s === 'preview' ? 'Preview' : 'Done'}
          </span>
        ))}
      </div>

      {/* Step 1: Upload */}
      {step === 'upload' && (
        <div style={styles.uploadArea}>
          <label style={styles.label}>Account</label>
          <select
            style={styles.input}
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
          >
            {accounts.map((a) => (
              <option key={a.node_id} value={a.node_id}>{a.title}</option>
            ))}
          </select>

          <div
            style={styles.dropZone}
            onClick={() => fileInputRef.current?.click()}
          >
            <p style={styles.dropText}>Click to select a CSV file</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={handleFileSelect}
            />
          </div>
        </div>
      )}

      {/* Step 2: Column Mapping */}
      {step === 'mapping' && (
        <div style={styles.mappingArea}>
          <p style={styles.mappingInfo}>
            Map CSV columns to transaction fields. File: {file?.name}
          </p>
          {MAPPABLE_FIELDS.map((field) => (
            <div key={field.key} style={styles.mappingRow}>
              <label style={styles.mappingLabel}>
                {field.label} {field.required && '*'}
              </label>
              <select
                style={styles.mappingSelect}
                value={mapping[field.key] || ''}
                onChange={(e) =>
                  setMapping((prev) => ({ ...prev, [field.key]: e.target.value }))
                }
              >
                <option value="">— Skip —</option>
                {csvHeaders.map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>
          ))}
          <div style={styles.actions}>
            <button style={styles.primaryBtn} onClick={handlePreview} disabled={loading}>
              {loading ? 'Previewing...' : 'Preview Import'}
            </button>
            <button style={styles.secondaryBtn} onClick={() => setStep('upload')}>
              Back
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Preview */}
      {step === 'preview' && preview && (
        <div style={styles.previewArea}>
          <div style={styles.previewSummary}>
            <span style={styles.summaryItem}>Total: {preview.total_rows}</span>
            <span style={{ ...styles.summaryItem, color: tokens.colors.success }}>
              Valid: {preview.valid_rows}
            </span>
            <span style={{ ...styles.summaryItem, color: tokens.colors.error }}>
              Errors: {preview.error_rows}
            </span>
            <span style={{ ...styles.summaryItem, color: tokens.colors.warning }}>
              Duplicates: {preview.duplicate_rows}
            </span>
          </div>

          <div style={styles.previewTable}>
            {preview.rows.slice(0, 20).map((row) => (
              <div
                key={row.row_number}
                style={{
                  ...styles.previewRow,
                  borderLeftColor: row.errors.length > 0
                    ? tokens.colors.error
                    : row.is_duplicate
                    ? tokens.colors.warning
                    : tokens.colors.success,
                }}
              >
                <span style={styles.rowNum}>#{row.row_number}</span>
                <span style={styles.rowData}>
                  {Object.entries(row.data).slice(0, 4).map(([k, v]) => `${k}: ${v}`).join(' | ')}
                </span>
                {row.errors.length > 0 && (
                  <span style={styles.rowError}>{row.errors[0]}</span>
                )}
                {row.is_duplicate && (
                  <span style={styles.rowDuplicate}>Duplicate</span>
                )}
              </div>
            ))}
            {preview.rows.length > 20 && (
              <div style={styles.moreRows}>...and {preview.rows.length - 20} more rows</div>
            )}
          </div>

          <div style={styles.actions}>
            <button
              style={styles.primaryBtn}
              onClick={handleImport}
              disabled={loading || preview.valid_rows === 0}
            >
              {loading ? 'Importing...' : `Import ${preview.valid_rows} Transactions`}
            </button>
            <button style={styles.secondaryBtn} onClick={() => setStep('mapping')}>
              Back to Mapping
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Result */}
      {step === 'result' && result && (
        <div style={styles.resultArea}>
          <div style={styles.resultCard}>
            <h3 style={styles.resultTitle}>Import Complete</h3>
            <div style={styles.resultRow}>
              <span>Imported:</span>
              <span style={{ color: tokens.colors.success }}>{result.imported_count}</span>
            </div>
            <div style={styles.resultRow}>
              <span>Skipped (duplicates):</span>
              <span style={{ color: tokens.colors.warning }}>{result.skipped_duplicates}</span>
            </div>
            <div style={styles.resultRow}>
              <span>Errors:</span>
              <span style={{ color: tokens.colors.error }}>{result.error_count}</span>
            </div>
            {result.balance_snapshots_created > 0 && (
              <div style={styles.resultRow}>
                <span>Balance snapshots created:</span>
                <span style={{ color: tokens.colors.accent }}>{result.balance_snapshots_created}</span>
              </div>
            )}
          </div>
          <button style={styles.primaryBtn} onClick={onClose}>
            Done
          </button>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', height: '100%' },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 18,
    color: tokens.colors.text,
    margin: 0,
  },
  closeButton: {
    padding: '4px 12px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    color: tokens.colors.textMuted,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    cursor: 'pointer',
  },
  error: {
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    padding: '8px 0',
  },
  steps: {
    display: 'flex',
    gap: 16,
    marginBottom: 16,
    paddingBottom: 12,
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  stepLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
  },
  uploadArea: { display: 'flex', flexDirection: 'column', gap: 12 },
  label: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 12,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  input: {
    padding: '8px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: tokens.colors.surface,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    outline: 'none',
  },
  dropZone: {
    padding: 32,
    border: `2px dashed ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    textAlign: 'center' as const,
    cursor: 'pointer',
    transition: 'border-color 0.15s',
  },
  dropText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.textMuted,
    margin: 0,
  },
  mappingArea: { display: 'flex', flexDirection: 'column', gap: 10 },
  mappingInfo: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    margin: '0 0 8px',
  },
  mappingRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  mappingLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    width: 120,
    flexShrink: 0,
  },
  mappingSelect: {
    flex: 1,
    padding: '6px 8px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: tokens.colors.surface,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    outline: 'none',
  },
  actions: { display: 'flex', gap: 8, marginTop: 16 },
  primaryBtn: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: 'none',
    background: tokens.colors.accent,
    color: '#000',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  secondaryBtn: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    color: tokens.colors.textMuted,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    cursor: 'pointer',
  },
  previewArea: { display: 'flex', flexDirection: 'column', gap: 12, flex: 1, overflow: 'hidden' },
  previewSummary: {
    display: 'flex',
    gap: 16,
    padding: '8px 0',
  },
  summaryItem: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
  },
  previewTable: {
    flex: 1,
    overflowY: 'auto',
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
  },
  previewRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '6px 10px',
    borderBottom: `1px solid ${tokens.colors.border}`,
    borderLeft: '3px solid transparent',
    fontSize: 12,
  },
  rowNum: { fontFamily: tokens.fonts.mono, fontSize: 10, color: tokens.colors.textMuted, width: 30, flexShrink: 0 },
  rowData: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.text,
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
  rowError: { fontFamily: tokens.fonts.sans, fontSize: 10, color: tokens.colors.error },
  rowDuplicate: { fontFamily: tokens.fonts.mono, fontSize: 10, color: tokens.colors.warning },
  moreRows: {
    padding: 8,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    textAlign: 'center' as const,
  },
  resultArea: { display: 'flex', flexDirection: 'column', gap: 16, alignItems: 'flex-start' },
  resultCard: {
    padding: 16,
    background: tokens.colors.surface,
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    width: '100%',
  },
  resultTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 16,
    color: tokens.colors.text,
    margin: '0 0 12px',
  },
  resultRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.text,
    padding: '4px 0',
  },
};
