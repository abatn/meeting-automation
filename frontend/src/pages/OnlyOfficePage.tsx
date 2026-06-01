import React from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import OnlyOfficeEditor from "../components/meetings/OnlyOfficeEditor";
import { Box } from "@mui/material";

const OnlyOfficePage: React.FC = () => {
  const { t } = useTranslation();
  const { pvId } = useParams<{ pvId: string }>();
  const [searchParams] = useSearchParams();
  const language = searchParams.get("lang") || "fr";

  if (!pvId) {
    return <Box sx={{ p: 3 }}>{t('pv.no_id_error')}</Box>;
  }

  return (
    <Box sx={{ width: "100vw", height: "100vh", overflow: "hidden" }}>
      <OnlyOfficeEditor
        pvId={pvId}
        language={language}
        onClose={() => window.close()}
      />
    </Box>
  );
};

export default OnlyOfficePage;
