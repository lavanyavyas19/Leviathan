import React, { useRef, useState } from "react";


const Sidebar = ({ activeView, setActiveView, setDatasetUploaded, datasetUploaded }) => {  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  const menuItems = [
    { id: "dashboard", label: "Dashboard" },
    { id: "vessel-logs", label: "Vessel Logs" },
    { id: "anomaly-reports", label: "Anomaly Reports" },
    { id: "audit-logs", label: "Audit Logs" },
    { id: "settings", label: "Settings" },
  ];

  // Handle dataset upload to backend
  const handleFileImport = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("http://localhost:8000/api/upload-ais-data", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Upload failed");

      const result = await response.json();
      alert(`✅ ${result.message}`);
      console.log("Processed File:", result);
      // ✅ Notify Dashboard that dataset has been uploaded
      if (setDatasetUploaded) {
      setDatasetUploaded(true);
     }

    } catch (error) {
      console.error("Error uploading file:", error);
      alert("❌ Error uploading AIS data. Please check the backend logs.");
    } finally {
      setUploading(false);
    }
  };

  const triggerFileImport = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="w-64 bg-slate-800/50 backdrop-blur-lg border-r border-cyan-500/20 p-4 flex flex-col">
      {/* Import Dataset Button */}
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
          {uploading ? (
            <svg
              className="animate-spin h-5 w-5 text-emerald-400"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8z"
              ></path>
            </svg>
          ) : (
            <>
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
              <span className="font-medium">Import Dataset</span>
            </>
          )}
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept=".json,.csv"
          onChange={handleFileImport}
          className="hidden"
        />

        <p className="text-xs text-gray-400 mt-1 text-center">
          Upload AIS data (JSON/CSV)
        </p>
      </div>

      {/* Navigation Menu */}
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