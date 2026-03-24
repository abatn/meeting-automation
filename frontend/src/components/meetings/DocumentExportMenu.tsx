import React, { useState } from "react";
import { Button, CircularProgress, Snackbar, Alert, Box, Select, MenuItem, FormControl } from "@mui/material";
import { PictureAsPdf as PdfIcon, Description as DocxIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import api from "../../services/api";

interface Props {
  pvId: string;
  language: string;
  fileName?: string;
  variant?: "contained" | "outlined" | "text";
  showDocx?: boolean;
}

const DocumentExportMenu: React.FC<Props> = ({
  pvId,
  language,
  fileName,
  variant = "contained",
  showDocx = true,
}) => {
  const { t } = useTranslation();
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [downloadingDocx, setDownloadingDocx] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async (format: "pdf" | "docx") => {
    try {
      if (format === "pdf") setDownloadingPdf(true);
      else setDownloadingDocx(true);
      
      setError(null);

      const response = await api.get(`/pv/${pvId}/${format}?language=${language}`, {
        responseType: "blob", 
      });

      const mimeType = format === "pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
      const blob = new Blob([response.data], { type: mimeType });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      
      const defaultName = `PV_${pvId}_${language}.${format}`;
      link.setAttribute("download", fileName ? `${fileName}.${format}` : defaultName);
      
      document.body.appendChild(link);
      link.click();

      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error(`Download ${format} failed`, err);
      setError(t("pv.download_error") || `Failed to download ${format}`);
    } finally {
      if (format === "pdf") setDownloadingPdf(false);
      else setDownloadingDocx(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
      <Button
        variant={variant}
        color="error"
        onClick={() => handleDownload("pdf")}
        disabled={downloadingPdf || downloadingDocx}
        startIcon={downloadingPdf ? <CircularProgress size={20} color="inherit" /> : <PdfIcon />}
      >
        PDF
      </Button>

      {showDocx && (
        <Button
          variant={variant}
          color="primary"
          onClick={() => handleDownload("docx")}
          disabled={downloadingPdf || downloadingDocx}
          startIcon={downloadingDocx ? <CircularProgress size={20} color="inherit" /> : <DocxIcon />}
        >
          Word
        </Button>
      )}

      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
        <Alert onClose={() => setError(null)} severity="error" sx={{ width: "100%" }}>
          {error}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default DocumentExportMenu;
