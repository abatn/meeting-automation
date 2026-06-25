import React, { useEffect, useRef, useState } from "react";
import { Box, CircularProgress, Typography, IconButton, AppBar, Toolbar } from "@mui/material";
import { Close as CloseIcon } from "@mui/icons-material";
import { onlyOfficeApi } from "../../services/onlyoffice";
import { useTranslation } from "react-i18next";

interface Props {
  pvId: string;
  language: string;
  onClose: () => void;
}

declare global {
  interface Window {
    DocsAPI: any;
  }
}

const OnlyOfficeEditor: React.FC<Props> = ({ pvId, language, onClose }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  const editorInstanceRef = useRef<any>(null);
  const [config, setConfig] = useState<any>(null);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const data = await onlyOfficeApi.getConfig(pvId, language);
        setConfig(data);
        setLoading(false);
      } catch (err) {
        console.error("Failed to load OnlyOffice config", err);
        setError(t("pv.editor_load_error"));
        setLoading(false);
      }
    };

    fetchConfig();
  }, [pvId, language]);

  useEffect(() => {
    if (!config || !editorRef.current) return;

    const destroyExistingEditor = () => {
      if (editorInstanceRef.current) {
        try {
          editorInstanceRef.current.destroy();
        } catch (e) {
          console.warn("OnlyOffice destroy failed:", e);
        }
        editorInstanceRef.current = null;
      }
      if (editorRef.current) {
        editorRef.current.innerHTML = "";
      }
    };

    destroyExistingEditor();

    const scriptId = "onlyoffice-api-script";
    let script = document.getElementById(scriptId) as HTMLScriptElement;

    const initEditor = () => {
      if (window.DocsAPI && editorRef.current) {
        try {
          editorInstanceRef.current = new window.DocsAPI.DocEditor("onlyoffice-editor-container", config);
        } catch (e) {
          console.error("OnlyOffice DocEditor init failed:", e);
          setError(t("pv.editor_load_error"));
        }
      }
    };

    if (!script) {
      script = document.createElement("script");
      script.id = scriptId;
      const baseUrl = config.editorConfig.customization?.onlyOfficeUrl || "http://localhost:8080";
      script.src = `${baseUrl}/web-apps/apps/api/documents/api.js`;
      script.onload = initEditor;
      document.body.appendChild(script);
    } else {
      if (window.DocsAPI) initEditor();
    }

    return () => {
      destroyExistingEditor();
    };
  }, [config, pvId]);

  if (loading) {
    return (
      <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" height="100vh">
        <CircularProgress />
        <Typography sx={{ mt: 2 }}>{t("pv.loading_editor") || "Loading Document Editor..."}</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={4} textAlign="center">
        <Typography color="error">{error}</Typography>
        <IconButton onClick={onClose} sx={{ mt: 2 }}><CloseIcon /></IconButton>
      </Box>
    );
  }

  return (
    <Box sx={{ height: "100vh", display: "flex", flexDirection: "column", bgcolor: "#f4f4f4" }}>
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar variant="dense">
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            {t("pv.edit_online_title") || "Edit Minutes Online"}
          </Typography>
          <IconButton edge="end" onClick={onClose}>
            <CloseIcon />
          </IconButton>
        </Toolbar>
      </AppBar>
      <Box 
        id="onlyoffice-editor-container" 
        ref={editorRef} 
        sx={{ flexGrow: 1, width: "100%" }} 
      />
    </Box>
  );
};

export default OnlyOfficeEditor;
