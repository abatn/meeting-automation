import React, { useState } from "react";
import {
  Button,
  TextField,
  Box,
  Typography,
  CircularProgress,
} from "@mui/material";
import { useTranslation } from "react-i18next";

interface MFASetupProps {
  qrCodeUrl: string;
  secret: string;
}

const MFASetup: React.FC<MFASetupProps> = ({ qrCodeUrl, secret }) => {
  const { t } = useTranslation();
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);

  const handleVerify = () => {
    // TODO: Handle OTP verification
    setLoading(true);
    console.log(otp);
    setLoading(false);
  };

  return (
    <Box>
      <Typography variant="h6">{t("mfaSetup")}</Typography>
      <Box my={2}>
        <img src={qrCodeUrl} alt={t('auth.mfa_qr_code_alt')} />
        <Typography>{t('auth.mfa_secret_label', { secret })}</Typography>
      </Box>
      <TextField
        label={t("otpCode")}
        value={otp}
        onChange={(e) => setOtp(e.target.value)}
        fullWidth
      />
      <Button
        onClick={handleVerify}
        variant="contained"
        disabled={loading}
        sx={{ mt: 2 }}
      >
        {loading ? <CircularProgress size={24} /> : t("verify")}
      </Button>
    </Box>
  );
};

export default MFASetup;
