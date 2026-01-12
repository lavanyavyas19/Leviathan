import { useState } from 'react';

function RawAISUploader() {
  const [file, setFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('');
  const [uploading, setUploading] = useState(false);

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      // Check file type (CSV or GZ)
      const validTypes = ['text/csv', 'application/gzip', 'application/x-gzip', 'application/x-compressed'];
      const validExtensions = ['.csv', '.gz', '.csv.gz'];
      const hasValidExtension = validExtensions.some(ext => selectedFile.name.toLowerCase().endsWith(ext));
      
      if (validTypes.includes(selectedFile.type) || hasValidExtension) {
        setFile(selectedFile);
        setUploadStatus(`File selected: ${selectedFile.name} (${(selectedFile.size / 1024 / 1024).toFixed(2)} MB)`);
      } else {
        setUploadStatus('Error: Only CSV or CSV.GZ files allowed!');
        setFile(null);
      }
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setUploadStatus('Please select a file first!');
      return;
    }

    setUploading(true);
    setUploadStatus('Uploading to S3...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      // Direct upload to FastAPI endpoint which handles S3 upload
      const response = await fetch('http://localhost:8000/api/upload-ais-data', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        setUploadStatus(`✓ Upload successful!\n📍 Location: ${data.s3_location}\n📦 Size: ${(data.size / 1024 / 1024).toFixed(2)} MB\n⏰ Auto-cleanup in 3 days`);
        setFile(null);
        // Clear the file input
        document.querySelector('input[type="file"]').value = '';
      } else {
        throw new Error(data.detail || 'Upload failed');
      }
    } catch (error) {
      setUploadStatus(`✗ Error: ${error.message}`);
      console.error('Upload error:', error);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-6 bg-gradient-to-br from-slate-800 to-slate-900 rounded-lg shadow-xl border border-cyan-500/20">
      <h2 className="text-2xl font-bold mb-4 text-cyan-400 flex items-center gap-2">
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        Upload Raw AIS Data
      </h2>
      
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Select CSV/CSV.GZ File
        </label>
        <input
          type="file"
          accept=".csv,.gz,.csv.gz"
          onChange={handleFileSelect}
          className="block w-full text-sm text-gray-400
            file:mr-4 file:py-2.5 file:px-4
            file:rounded-lg file:border-0
            file:text-sm file:font-semibold
            file:bg-cyan-600 file:text-white
            hover:file:bg-cyan-700
            file:cursor-pointer
            border border-gray-600 rounded-lg
            bg-slate-700/50
            cursor-pointer
            focus:outline-none focus:ring-2 focus:ring-cyan-500"
          disabled={uploading}
        />
      </div>
      
      <button
        onClick={handleUpload}
        disabled={!file || uploading}
        className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 text-white px-6 py-3 rounded-lg
          font-semibold text-sm
          hover:from-cyan-700 hover:to-blue-700
          disabled:from-gray-600 disabled:to-gray-700
          disabled:cursor-not-allowed
          transition-all duration-200
          shadow-lg hover:shadow-cyan-500/50
          flex items-center justify-center gap-2"
      >
        {uploading ? (
          <>
            <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Uploading to S3...
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            Upload to S3 Raw Bucket
          </>
        )}
      </button>
      
      {uploadStatus && (
        <div className={`mt-4 p-4 rounded-lg text-sm font-mono whitespace-pre-line ${
          uploadStatus.startsWith('✓') 
            ? 'bg-green-900/30 text-green-400 border border-green-500/30' 
            : uploadStatus.startsWith('✗') 
            ? 'bg-red-900/30 text-red-400 border border-red-500/30' 
            : 'bg-blue-900/30 text-blue-400 border border-blue-500/30'
        }`}>
          {uploadStatus}
        </div>
      )}

      <div className="mt-4 p-3 bg-slate-700/30 rounded-lg border border-slate-600">
        <p className="text-xs text-gray-400">
          <span className="font-semibold text-cyan-400">ℹ️ Info:</span> Files are uploaded to S3 raw bucket and auto-deleted after 3 days. Preprocessing happens separately via batch job.
        </p>
      </div>
    </div>
  );
}

export default RawAISUploader;
