import React, { useRef, useState } from "react";

const Sidebar = ({ activeView, setActiveView, setDatasetUploaded }) => {
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("");

  const menuItems = [
    { id: "dashboard", label: "Dashboard" },
    { id: "vessel-logs", label: "Vessel Logs" },
    { id: "anomaly-reports", label: "Anomaly Reports" },
    { id: "audit-logs", label: "Audit Logs" },
    { id: "settings", label: "Settings" },
  ];

  const handleFileImport = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // allow re-uploading same file again
    event.target.value = "";

    setUploading(true);
    setProgress(0);
    setStatusText(`Uploading ${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)...`);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const result = await uploadWithProgress(
        "http://localhost:8000/api/upload-ais-data",
        formData,
        (p) => setProgress(p)
      );

      setStatusText("Upload complete. Processing…");

      const jobId = result.job_id;

const poll = setInterval(async () => {
  const res = await fetch(`http://localhost:8000/api/jobs/${jobId}`);
  const job = await res.json();

  if (job.status === "done") {
    clearInterval(poll);
    setDatasetUploaded(true);
    alert("✅ Dataset processed successfully!");
  }

  if (job.status === "failed") {
    clearInterval(poll);
    alert("❌ Processing failed");
  }
}, 3000);


      setDatasetUploaded?.(true);
      setStatusText("Done ✅");
    } catch (error) {
      console.error("Error uploading file:", error);
      setStatusText("Upload failed ❌ (check backend logs)");
      alert("❌ Error uploading AIS data. Please check the backend logs.");
    } finally {
      setUploading(false);
    }
  };

  function uploadWithProgress(url, formData, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.open("POST", url);

      // Upload progress
      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable) return;
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(percent);
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch (e) {
            reject(new Error("Invalid JSON response from server"));
          }
        } else {
          reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`));
        }
      };

      xhr.onerror = () => reject(new Error("Network error during upload"));

      xhr.send(formData);
    });
  }

  const triggerFileImport = () => fileInputRef.current?.click();

  return (
    <div className="w-64 bg-slate-800/50 backdrop-blur-lg border-r border-cyan-500/20 p-4 flex flex-col">
      <div className="mb-6">
        <button
          onClick={triggerFileImport}
          disabled={uploading}
          className={`w-full flex items-center justify-center space-x-2 px-4 py-3 rounded-lg border transition-all duration-200 ${
            uploading
              ? "bg-gray-500/30 border-gray-400/30 cursor-not-allowed"
              : "bg-gradient-to-r from-emerald-600/30 to-teal-600/30 hover:from-emerald-600/40 hover:to-teal-600/40 border-emerald-500/50 shadow-lg shadow-emerald-500/20 text-emerald-400"
          }`}
        >
          <span className="font-medium">
            {uploading ? `Uploading… ${progress}%` : "Import Dataset"}
          </span>
        </button>

        {/* ✅ Fix Chrome issues: label + autocomplete */}
        <label htmlFor="aisFile" className="sr-only">
          Upload AIS dataset
        </label>
        <input
          id="aisFile"
          ref={fileInputRef}
          type="file"
          accept=".csv,.json,.gz,.csv.gz"
          autoComplete="off"
          onChange={handleFileImport}
          className="hidden"
        />

        {/* Progress bar */}
        {uploading && (
          <div className="mt-3">
            <div className="w-full h-2 bg-slate-700 rounded">
              <div
                className="h-2 rounded bg-emerald-400 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-gray-300 mt-2">{statusText}</p>
          </div>
        )}

        {!uploading && (
          <p className="text-xs text-gray-400 mt-1 text-center">
            Upload AIS data (CSV/JSON/CSV.GZ)
          </p>
        )}
      </div>

      <nav className="space-y-2 flex-1">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${
              activeView === item.id
                ? "bg-gradient-to-r from-cyan-600/30 to-teal-600/30 border border-cyan-500/50 shadow-lg shadow-cyan-500/20"
                : "hover:bg-slate-700/50 border border-transparent"
            }`}
          >
            <span className="font-medium">{item.label}</span>
            {activeView === item.id && (
              <div className="ml-auto w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></div>
            )}
          </button>
        ))}
      </nav>
    </div>
  );
};

export default Sidebar;
