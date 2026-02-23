import React, { useState } from 'react';
import { Button, CircularProgress, Snackbar, Alert } from '@mui/material';
import { PictureAsPdf as PdfIcon } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import api from '../../services/api';

interface Props {
  pvId: number;
  fileName?: string;
  variant?: 'contained' | 'outlined' | 'text';
}

const PDFDownloadButton: React.FC<Props> = ({ pvId, fileName, variant = 'contained' }) => {
  const { t } = useTranslation();
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async () => {
    try {
      setDownloading(true);
      setError(null);
      
      const response = await api.get(`/pv/${pvId}/pdf`, {
        responseType: 'blob', // Wichtig für Datei-Downloads
      });

      // Erstelle Blob aus der Response
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', fileName || `PV_${pvId}.pdf`); // Name der Datei
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
      
    } catch (err: any) {
      console.error('Download failed', err);
      setError(t('pv.download_error', 'Fehler beim Herunterladen des PDFs'));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <>
      <Button
        variant={variant}
        color="primary"
        onClick={handleDownload}
        disabled={downloading}
        startIcon={downloading ? <CircularProgress size={20} color="inherit" /> : <PdfIcon />}
        sx={{ minWidth: 120 }}
      >
        {downloading ? t('common.downloading', 'جاري التحميل...') : t('pv.download_pdf', 'تحميل PDF')}
      </Button>
      
      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
        <Alert onClose={() => setError(null)} severity="error" sx={{ width: '100%' }}>
          {error}
        </Alert>
      </Snackbar>
    </>
  );
};

export default PDFDownloadButton;
