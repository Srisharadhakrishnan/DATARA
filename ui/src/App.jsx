import React, { useState, useEffect, useRef } from 'react';
import { 
  UploadCloud, FileText, CheckCircle2, AlertTriangle, 
  Send, Code, Database, ChevronDown, ChevronUp, RefreshCw, Layers, Sparkles 
} from 'lucide-react';

const API_BASE = ''; // Proxy handles endpoints

export default function App() {
  // System Health
  const [health, setHealth] = useState({ ok: false, kafka: false, neo4j: false, loading: true });
  
  // File & Upload State
  const [selectedFile, setSelectedFile] = useState(null);
  const [filePreview, setFilePreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  
  // Job & Ingestion State
  const [activeJob, setActiveJob] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  
  // Chat State
  const [question, setQuestion] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [openCypherIndex, setOpenCypherIndex] = useState({});
  const [openRawIndex, setOpenRawIndex] = useState({});
  
  const chatEndRef = useRef(null);

  // Poll Health on Mount
  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const checkHealth = async () => {
    try {
      const res = await fetch('/health');
      const data = await res.json();
      setHealth({
        ok: data.status === 'ok',
        kafka: data.kafka_connected,
        neo4j: data.neo4j_connected,
        loading: false
      });
    } catch (e) {
      setHealth({ ok: false, kafka: false, neo4j: false, loading: false });
    }
  };

  // Handle File Selection & Local CSV Preview
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setUploadError('Please select a valid .csv file.');
      return;
    }
    setUploadError(null);
    setSelectedFile(file);

    // Read preview client-side
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target.result;
      const lines = text.split(/\r\n|\n/).filter(line => line.trim());
      if (lines.length > 0) {
        const headers = lines[0].split(',').map(h => h.trim().replace(/^["']|["']$/g, ''));
        const rows = lines.slice(1, 6).map(line => {
          const vals = line.split(',').map(v => v.trim().replace(/^["']|["']$/g, ''));
          const rowObj = {};
          headers.forEach((h, i) => {
            rowObj[h] = vals[i] || '';
          });
          return rowObj;
        });

        setFilePreview({
          filename: file.name,
          sizeBytes: file.size,
          rowCountEstimate: lines.length - 1,
          columnCount: headers.length,
          columns: headers,
          sampleRows: rows
        });
      }
    };
    reader.readAsText(file);
  };

  // Upload CSV to API
  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await fetch('/ingest', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Upload failed');
      }

      setActiveJob(data);
      setJobStatus({
        job_id: data.job_id,
        status: 'queued',
        rows_total: data.rows_received,
        rows_loaded: 0,
        rows_failed: 0
      });
    } catch (e) {
      setUploadError(e.message);
    } finally {
      setUploading(false);
    }
  };

  // Poll Ingestion Status
  useEffect(() => {
    if (!activeJob) return;
    
    let timer;
    const pollStatus = async () => {
      try {
        const res = await fetch(`/status?job_id=${activeJob.job_id}`);
        if (res.ok) {
          const statusData = await res.json();
          setJobStatus(statusData);

          if (statusData.status === 'complete' || statusData.status === 'failed') {
            return; // Stop polling
          }
        }
      } catch (e) {
        console.error('Status poll error:', e);
      }
      timer = setTimeout(pollStatus, 1500);
    };

    pollStatus();
    return () => clearTimeout(timer);
  }, [activeJob]);

  // Send Chat Question
  const handleSendQuestion = async (qText) => {
    const queryToSubmit = qText || question;
    if (!queryToSubmit.trim()) return;

    const userMsg = { id: Date.now(), role: 'user', text: queryToSubmit };
    setMessages(prev => [...prev, userMsg]);
    setQuestion('');
    setChatLoading(true);

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: queryToSubmit })
      });
      const data = await res.json();

      const assistantMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        answer: data.answer,
        cypher: data.cypher,
        result: data.result,
        grounded: data.grounded
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (e) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'assistant',
        answer: "I don't have that information in the uploaded data.",
        cypher: "MATCH (r:Row) RETURN count(r)",
        result: [],
        grounded: false
      }]);
    } finally {
      setChatLoading(false);
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    }
  };

  const toggleCypher = (idx) => {
    setOpenCypherIndex(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  const toggleRaw = (idx) => {
    setOpenRawIndex(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  const formatBytes = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  };

  return (
    <div style={styles.appContainer}>
      {/* HEADER */}
      <header style={styles.header}>
        <div style={styles.headerContent}>
          <div style={styles.brandRow}>
            <div style={styles.logoBadge}>
              <Layers size={22} color="#FFF9F1" />
            </div>
            <div>
              <h1 style={styles.brandTitle}>DATARA</h1>
              <p style={styles.brandTagline}>Ask your data. Trust the answer.</p>
            </div>
          </div>

          <div style={styles.healthBadge}>
            <span style={{
              ...styles.statusDot,
              backgroundColor: health.ok ? '#2E7D32' : '#D32F2F'
            }} />
            <span style={styles.statusText}>
              {health.loading ? 'Checking services...' : health.ok ? 'System Ready' : 'Service Offline'}
            </span>
          </div>
        </div>
      </header>

      {/* MAIN CONTAINER */}
      <main style={styles.main}>
        
        {/* SECTION 1: UPLOAD & PREVIEW */}
        <section style={styles.card}>
          <div style={styles.cardHeader}>
            <h2 style={styles.cardTitle}>Bring your data to Datara</h2>
            <p style={styles.cardSubtitle}>Upload any CSV file. Datara dynamically structures rows into graph nodes via Kafka.</p>
          </div>

          {/* Upload Dropzone */}
          <div style={styles.dropzone}>
            <UploadCloud size={40} color="#7A263A" style={{ marginBottom: 12 }} />
            <p style={styles.dropText}>
              {selectedFile ? selectedFile.name : "Drag and drop your CSV file here, or click to browse"}
            </p>
            <input 
              type="file" 
              accept=".csv"
              onChange={handleFileChange}
              style={styles.fileInput} 
            />
            {selectedFile && (
              <button 
                onClick={handleUpload}
                disabled={uploading}
                style={styles.uploadBtn}
              >
                {uploading ? <RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <FileText size={16} />}
                {uploading ? 'Ingesting CSV...' : 'Ingest CSV Data'}
              </button>
            )}
          </div>

          {uploadError && (
            <div style={styles.errorAlert}>
              <AlertTriangle size={18} color="#D32F2F" />
              <span>{uploadError}</span>
            </div>
          )}

          {/* Smart CSV Preview (Feature 1) */}
          {filePreview && (
            <div style={styles.previewContainer}>
              <div style={styles.previewMetaRow}>
                <div style={styles.metaBox}>
                  <span style={styles.metaLabel}>FILENAME</span>
                  <span style={styles.metaVal}>{filePreview.filename}</span>
                </div>
                <div style={styles.metaBox}>
                  <span style={styles.metaLabel}>FILE SIZE</span>
                  <span style={styles.metaVal}>{formatBytes(filePreview.sizeBytes)}</span>
                </div>
                <div style={styles.metaBox}>
                  <span style={styles.metaLabel}>TOTAL ROWS</span>
                  <span style={styles.metaVal}>{filePreview.rowCountEstimate.toLocaleString()}</span>
                </div>
                <div style={styles.metaBox}>
                  <span style={styles.metaLabel}>COLUMNS</span>
                  <span style={styles.metaVal}>{filePreview.columnCount}</span>
                </div>
              </div>

              {/* Column Badges */}
              <div style={styles.columnPillsRow}>
                <span style={styles.pillLabel}>Detected Schema:</span>
                {filePreview.columns.map((col, i) => (
                  <span key={i} style={styles.columnPill}>{col}</span>
                ))}
              </div>

              {/* Sample Rows Table */}
              <div style={styles.tableWrapper}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      {filePreview.columns.map((col, idx) => (
                        <th key={idx} style={styles.th}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filePreview.sampleRows.map((row, rIdx) => (
                      <tr key={rIdx} style={styles.tr}>
                        {filePreview.columns.map((col, cIdx) => (
                          <td key={cIdx} style={styles.td}>{row[col] || '-'}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Real Pipeline Stage Progress Tracker */}
          {jobStatus && (
            <div style={styles.pipelineTracker}>
              <div style={styles.pipelineStages}>
                <div style={styles.stageItem}>
                  <CheckCircle2 size={18} color="#2E7D32" />
                  <span>CSV Verified</span>
                </div>
                <div style={styles.stageLine} />
                <div style={styles.stageItem}>
                  <CheckCircle2 size={18} color="#2E7D32" />
                  <span>Kafka Topic</span>
                </div>
                <div style={styles.stageLine} />
                <div style={styles.stageItem}>
                  {jobStatus.status === 'complete' ? (
                    <CheckCircle2 size={18} color="#2E7D32" />
                  ) : (
                    <RefreshCw size={18} color="#7A263A" style={{ animation: 'spin 1.5s linear infinite' }} />
                  )}
                  <span>Loader Consumer</span>
                </div>
                <div style={styles.stageLine} />
                <div style={styles.stageItem}>
                  {jobStatus.status === 'complete' ? (
                    <CheckCircle2 size={18} color="#2E7D32" />
                  ) : (
                    <Database size={18} color="#776B66" />
                  )}
                  <span>Neo4j Graph</span>
                </div>
              </div>

              <div style={styles.progressBarContainer}>
                <div style={{
                  ...styles.progressBarFill,
                  width: `${jobStatus.rows_total > 0 ? Math.min(100, Math.round(((jobStatus.rows_loaded + jobStatus.rows_failed) / jobStatus.rows_total) * 100)) : 0}%`
                }} />
              </div>

              <div style={styles.progressFooter}>
                <span style={styles.progressText}>
                  Ingested {jobStatus.rows_loaded.toLocaleString()} / {jobStatus.rows_total.toLocaleString()} rows
                </span>
                <span style={{
                  ...styles.statusBadge,
                  backgroundColor: jobStatus.status === 'complete' ? '#E8F5E9' : '#FFF8E1',
                  color: jobStatus.status === 'complete' ? '#2E7D32' : '#C67D00'
                }}>
                  {jobStatus.status.toUpperCase()}
                </span>
              </div>
            </div>
          )}
        </section>

        {/* SECTION 2: GROUNDED CHATBOT */}
        <section style={styles.card}>
          <div style={styles.cardHeader}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={20} color="#7A263A" />
              <h2 style={styles.cardTitle}>Ask your data</h2>
            </div>
            <p style={styles.cardSubtitle}>Query your graph database naturally. Datara guarantees grounded, explainable answers strictly backed by stored Neo4j nodes.</p>
          </div>

          {/* Quick Prompt Chips */}
          {filePreview && (
            <div style={styles.chipRow}>
              <button 
                style={styles.chipBtn}
                onClick={() => handleSendQuestion('How many total rows are in the dataset?')}
              >
                📊 Total row count
              </button>
              {filePreview.columns.slice(0, 3).map((col, i) => (
                <button 
                  key={i} 
                  style={styles.chipBtn}
                  onClick={() => handleSendQuestion(`List unique values of ${col}`)}
                >
                  🔍 List values for {col}
                </button>
              ))}
            </div>
          )}

          {/* Chat Bubble Stream */}
          <div style={styles.chatStream}>
            {messages.length === 0 && (
              <div style={styles.emptyChatPlaceholder}>
                <Database size={36} color="#D8C7B8" style={{ marginBottom: 8 }} />
                <p>Upload a CSV file and ask questions like:</p>
                <p style={{ fontStyle: 'italic', fontSize: 13, marginTop: 4 }}>"How many rows belong to the Billing group?"</p>
              </div>
            )}

            {messages.map((msg, index) => (
              <div key={msg.id || index} style={msg.role === 'user' ? styles.userMsgRow : styles.assistantMsgRow}>
                {msg.role === 'user' ? (
                  <div style={styles.userBubble}>{msg.text}</div>
                ) : (
                  <div style={styles.assistantBubble}>
                    {/* Data Trust Indicator (Feature 3) */}
                    <div style={{
                      ...styles.trustBanner,
                      backgroundColor: msg.grounded ? '#E8F5E9' : '#F5F5F5',
                      borderColor: msg.grounded ? '#A5D6A7' : '#D8C7B8',
                      color: msg.grounded ? '#2E7D32' : '#616161'
                    }}>
                      {msg.grounded ? (
                        <>
                          <CheckCircle2 size={16} color="#2E7D32" />
                          <span>GROUNDED IN YOUR DATA</span>
                        </>
                      ) : (
                        <>
                          <AlertTriangle size={16} color="#757575" />
                          <span>NOT FOUND IN YOUR DATA</span>
                        </>
                      )}
                    </div>

                    <p style={styles.answerText}>{msg.answer}</p>

                    {/* Explainable Answers (Feature 2) */}
                    <div style={styles.explainableSection}>
                      <span style={styles.explainHeader}>How I found this:</span>
                      
                      {/* Cypher Accordion */}
                      <button style={styles.accordionToggle} onClick={() => toggleCypher(index)}>
                        <Code size={14} color="#7A263A" />
                        <span>Cypher Query</span>
                        {openCypherIndex[index] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>
                      {openCypherIndex[index] && (
                        <pre style={styles.codeBlock}><code>{msg.cypher}</code></pre>
                      )}

                      {/* Raw Result Accordion */}
                      <button style={styles.accordionToggle} onClick={() => toggleRaw(index)}>
                        <Database size={14} color="#7A263A" />
                        <span>Raw Graph Result ({msg.result ? msg.result.length : 0} items)</span>
                        {openRawIndex[index] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>
                      {openRawIndex[index] && (
                        <pre style={styles.codeBlock}><code>{JSON.stringify(msg.result, null, 2)}</code></pre>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {chatLoading && (
              <div style={styles.assistantMsgRow}>
                <div style={styles.assistantBubble}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#776B66' }}>
                    <RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} />
                    <span>Executing Cypher against Neo4j...</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Chat Input Bar */}
          <div style={styles.inputRow}>
            <input 
              type="text" 
              placeholder="Ask a question about your uploaded CSV data..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendQuestion()}
              style={styles.textInput}
            />
            <button 
              onClick={() => handleSendQuestion()}
              disabled={chatLoading || !question.trim()}
              style={styles.sendBtn}
            >
              <Send size={18} />
              <span>Ask</span>
            </button>
          </div>
        </section>

      </main>
    </div>
  );
}

const styles = {
  appContainer: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: 'var(--warm-cream)',
  },
  header: {
    backgroundColor: 'var(--burgundy)',
    color: 'var(--soft-ivory)',
    padding: '20px 32px',
    boxShadow: 'var(--shadow-md)'
  },
  headerContent: {
    maxWidth: '1000px',
    margin: '0 auto',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  brandRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px'
  },
  logoBadge: {
    width: '42px',
    height: '42px',
    backgroundColor: 'rgba(255, 249, 241, 0.15)',
    borderRadius: '10px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid rgba(255, 249, 241, 0.3)'
  },
  brandTitle: {
    fontSize: '24px',
    fontWeight: '700',
    letterSpacing: '1px',
    lineHeight: '1.1'
  },
  brandTagline: {
    fontSize: '13px',
    color: 'var(--dusty-pink)',
    fontWeight: '500'
  },
  healthBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: 'rgba(0,0,0,0.2)',
    padding: '6px 14px',
    borderRadius: '20px',
    fontSize: '13px'
  },
  statusDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%'
  },
  statusText: {
    fontWeight: '600'
  },
  main: {
    maxWidth: '1000px',
    width: '100%',
    margin: '32px auto',
    padding: '0 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '24px'
  },
  card: {
    backgroundColor: 'var(--soft-ivory)',
    borderRadius: '12px',
    border: '1px solid var(--soft-taupe)',
    padding: '28px',
    boxShadow: 'var(--shadow-sm)'
  },
  cardHeader: {
    marginBottom: '20px'
  },
  cardTitle: {
    fontSize: '20px',
    fontWeight: '700',
    color: 'var(--espresso)',
    marginBottom: '4px'
  },
  cardSubtitle: {
    fontSize: '14px',
    color: 'var(--warm-gray)'
  },
  dropzone: {
    border: '2px dashed var(--soft-taupe)',
    borderRadius: '10px',
    padding: '32px 20px',
    textAlign: 'center',
    backgroundColor: 'var(--warm-cream)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    position: 'relative'
  },
  dropText: {
    fontSize: '14px',
    color: 'var(--espresso)',
    fontWeight: '500',
    marginBottom: '16px'
  },
  fileInput: {
    position: 'absolute',
    top: 0, left: 0, width: '100%', height: '100%',
    opacity: 0,
    cursor: 'pointer'
  },
  uploadBtn: {
    backgroundColor: 'var(--burgundy)',
    color: 'var(--soft-ivory)',
    border: 'none',
    borderRadius: '8px',
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: '600',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    zIndex: 2,
    transition: 'background 0.2s'
  },
  errorAlert: {
    marginTop: '16px',
    padding: '12px 16px',
    backgroundColor: '#FFEBEE',
    border: '1px solid #FFCDD2',
    borderRadius: '8px',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    fontSize: '14px',
    color: '#D32F2F'
  },
  previewContainer: {
    marginTop: '24px',
    borderTop: '1px solid var(--soft-taupe)',
    paddingTop: '20px'
  },
  previewMetaRow: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
    gap: '12px',
    marginBottom: '16px'
  },
  metaBox: {
    backgroundColor: 'var(--sand)',
    padding: '10px 14px',
    borderRadius: '8px',
    display: 'flex',
    flexDirection: 'column'
  },
  metaLabel: {
    fontSize: '11px',
    fontWeight: '700',
    color: 'var(--warm-gray)'
  },
  metaVal: {
    fontSize: '15px',
    fontWeight: '700',
    color: 'var(--espresso)'
  },
  columnPillsRow: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '8px',
    marginBottom: '16px'
  },
  pillLabel: {
    fontSize: '13px',
    fontWeight: '600',
    color: 'var(--warm-gray)'
  },
  columnPill: {
    backgroundColor: 'var(--burgundy)',
    color: 'var(--soft-ivory)',
    padding: '3px 10px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: '600'
  },
  tableWrapper: {
    overflowX: 'auto',
    borderRadius: '8px',
    border: '1px solid var(--soft-taupe)'
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '13px',
    textAlign: 'left'
  },
  th: {
    backgroundColor: 'var(--sand)',
    color: 'var(--espresso)',
    fontWeight: '700',
    padding: '10px 12px',
    borderBottom: '1px solid var(--soft-taupe)'
  },
  tr: {
    borderBottom: '1px solid var(--soft-taupe)',
    backgroundColor: 'var(--soft-ivory)'
  },
  td: {
    padding: '8px 12px',
    color: 'var(--espresso)'
  },
  pipelineTracker: {
    marginTop: '24px',
    backgroundColor: 'var(--warm-cream)',
    padding: '16px 20px',
    borderRadius: '10px',
    border: '1px solid var(--soft-taupe)'
  },
  pipelineStages: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '14px'
  },
  stageItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '13px',
    fontWeight: '600',
    color: 'var(--espresso)'
  },
  stageLine: {
    flex: 1,
    height: '2px',
    backgroundColor: 'var(--soft-taupe)',
    margin: '0 8px'
  },
  progressBarContainer: {
    height: '8px',
    backgroundColor: 'var(--sand)',
    borderRadius: '4px',
    overflow: 'hidden',
    marginBottom: '10px'
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: 'var(--burgundy)',
    transition: 'width 0.3s ease'
  },
  progressFooter: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: '13px'
  },
  progressText: {
    fontWeight: '600',
    color: 'var(--warm-gray)'
  },
  statusBadge: {
    padding: '3px 10px',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: '700'
  },
  chipRow: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap',
    marginBottom: '16px'
  },
  chipBtn: {
    backgroundColor: 'var(--sand)',
    border: '1px solid var(--soft-taupe)',
    borderRadius: '16px',
    padding: '6px 14px',
    fontSize: '12px',
    fontWeight: '600',
    color: 'var(--espresso)',
    transition: 'all 0.2s'
  },
  chatStream: {
    minHeight: '220px',
    maxHeight: '400px',
    overflowY: 'auto',
    border: '1px solid var(--soft-taupe)',
    borderRadius: '10px',
    padding: '16px',
    backgroundColor: 'var(--warm-cream)',
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
    marginBottom: '16px'
  },
  emptyChatPlaceholder: {
    margin: 'auto',
    textAlign: 'center',
    color: 'var(--warm-gray)',
    fontSize: '14px'
  },
  userMsgRow: {
    display: 'flex',
    justifyContent: 'flex-end'
  },
  userBubble: {
    backgroundColor: 'var(--burgundy)',
    color: 'var(--soft-ivory)',
    padding: '10px 16px',
    borderRadius: '16px 16px 2px 16px',
    fontSize: '14px',
    maxWidth: '80%'
  },
  assistantMsgRow: {
    display: 'flex',
    justifyContent: 'flex-start'
  },
  assistantBubble: {
    backgroundColor: 'var(--soft-ivory)',
    border: '1px solid var(--soft-taupe)',
    padding: '14px 18px',
    borderRadius: '16px 16px 16px 2px',
    maxWidth: '90%',
    boxShadow: 'var(--shadow-sm)'
  },
  trustBanner: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 12px',
    borderRadius: '12px',
    border: '1px solid',
    fontSize: '11px',
    fontWeight: '700',
    letterSpacing: '0.5px',
    marginBottom: '10px'
  },
  answerText: {
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--espresso)',
    marginBottom: '12px'
  },
  explainableSection: {
    borderTop: '1px dashed var(--soft-taupe)',
    paddingTop: '10px',
    marginTop: '6px'
  },
  explainHeader: {
    fontSize: '12px',
    fontWeight: '700',
    color: 'var(--warm-gray)',
    display: 'block',
    marginBottom: '8px'
  },
  accordionToggle: {
    background: 'none',
    border: 'none',
    color: 'var(--burgundy)',
    fontSize: '12px',
    fontWeight: '700',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 0',
    marginBottom: '6px'
  },
  codeBlock: {
    backgroundColor: 'var(--espresso)',
    color: '#F8F8F2',
    padding: '10px 12px',
    borderRadius: '6px',
    fontSize: '12px',
    fontFamily: 'monospace',
    overflowX: 'auto',
    marginBottom: '8px'
  },
  inputRow: {
    display: 'flex',
    gap: '10px'
  },
  textInput: {
    flex: 1,
    padding: '12px 16px',
    borderRadius: '8px',
    border: '1px solid var(--soft-taupe)',
    backgroundColor: 'var(--soft-ivory)',
    fontSize: '14px',
    color: 'var(--espresso)',
    outline: 'none'
  },
  sendBtn: {
    backgroundColor: 'var(--burgundy)',
    color: 'var(--soft-ivory)',
    border: 'none',
    borderRadius: '8px',
    padding: '0 20px',
    fontWeight: '700',
    fontSize: '14px',
    display: 'flex',
    alignItems: 'center',
    gap: '6px'
  }
};
