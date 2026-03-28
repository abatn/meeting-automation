import React, { useState } from 'react';
import { 
  Box, Container, Typography, Button, Grid, Stack,
  AppBar, Toolbar, Link as MuiLink, Divider,
  Menu, MenuItem, CssBaseline, Tooltip, Chip, Avatar,
  IconButton, useTheme, useMediaQuery, Drawer, List, ListItem, ListItemText
} from '@mui/material';
import { 
  AutoFixHigh as IAIcon, AssignmentTurnedIn as ActionIcon, GraphicEq as VoiceIcon,
  CheckCircle as CheckIcon, Security as ShieldIcon, 
  WhatsApp as WhatsAppIcon, Public as GlobalIcon,
  Description as EditIcon, Translate as TranslateIcon, 
  Memory as ChipIcon, WorkspacePremium as PremiumIcon,
  ArrowForward as ArrowIcon, Login as LoginIcon,
  Menu as MenuIcon
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';

const fadeIn = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } }
};

const LandingPage: React.FC = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const theme = useTheme();
  const isRtl = i18n.dir() === 'rtl';
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const [anchorElLang, setAnchorElLang] = useState<null | HTMLElement>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleOpenLangMenu = (event: React.MouseEvent<HTMLElement>) => setAnchorElLang(event.currentTarget);
  const handleCloseLangMenu = () => setAnchorElLang(null);
  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    handleCloseLangMenu();
  };

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      window.scrollTo({ top: element.getBoundingClientRect().top + window.scrollY - 80, behavior: 'smooth' });
    }
    setMobileMenuOpen(false);
  };

  const languages = [
    { code: 'en', label: 'English' },
    { code: 'fr-TN', label: 'Français' },
    { code: 'ar-TN', label: 'العربية' },
  ];

  return (
    <Box sx={{ 
      bgcolor: '#050505', 
      minHeight: '100vh', 
      color: '#FAFAFA', 
      direction: i18n.dir(),
      overflowX: 'hidden'
    }}>
      <CssBaseline />
      
      <style>
        {`
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Arabic:wght@400;500;700&display=swap');
          
          .glass-card {
            background: rgba(255, 255, 255, 0.02);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          }
          .glass-card:hover {
            background: rgba(255, 255, 255, 0.04);
            border-color: rgba(255, 255, 255, 0.1);
            transform: translateY(-4px);
          }
        `}
      </style>

      {/* --- NAVIGATION --- */}
      <AppBar position="fixed" elevation={0} sx={{ bgcolor: 'rgba(5, 5, 5, 0.8)', backdropFilter: 'blur(12px)', borderBottom: '1px solid rgba(255,255,255,0.06)', zIndex: 1201 }}>
        <Container maxWidth="lg">
          <Toolbar disableGutters sx={{ justifyContent: 'space-between', height: 64 }}>
            {/* Logo */}
            <Stack direction="row" alignItems="center" sx={{ cursor: 'pointer' }} onClick={() => window.scrollTo({top: 0, behavior: 'smooth'})}>
              <Box sx={{ width: 28, height: 28, bgcolor: '#FFF', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', mx: 1.5 }}>
                <IAIcon sx={{ color: '#000', fontSize: 16 }} />
              </Box>
              <Typography variant="h6" fontWeight="700" sx={{ letterSpacing: '-0.5px', color: 'white', fontSize: '1.1rem' }}>
                {t('common.appNamePart1')}<Box component="span" sx={{ color: '#71717A' }}>{t('common.appNamePart2')}</Box>
              </Typography>
            </Stack>

            {/* Desktop Menu */}
            {!isMobile && (
              <Stack direction="row" spacing={4} alignItems="center">
                <MuiLink component="button" onClick={() => scrollToSection('features')} variant="body2" sx={{ color: '#A1A1AA', textDecoration: 'none', fontWeight: 500, '&:hover': { color: '#FFF' } }}>{t('landing.nav.features')}</MuiLink>
                <MuiLink component="button" onClick={() => scrollToSection('pricing')} variant="body2" sx={{ color: '#A1A1AA', textDecoration: 'none', fontWeight: 500, '&:hover': { color: '#FFF' } }}>{t('landing.nav.pricing')}</MuiLink>
                
                <Divider orientation="vertical" flexItem sx={{ borderColor: 'rgba(255,255,255,0.1)', height: 20 }} />

                <Button onClick={handleOpenLangMenu} startIcon={<TranslateIcon sx={{fontSize: 18}} />} sx={{ color: '#A1A1AA', textTransform: 'none', fontWeight: 500 }}>
                  {i18n.language.split('-')[0].toUpperCase()}
                </Button>
                <Menu anchorEl={anchorElLang} open={Boolean(anchorElLang)} onClose={handleCloseLangMenu}>
                  {languages.map((l) => (
                    <MenuItem key={l.code} onClick={() => changeLanguage(l.code)}>{l.label}</MenuItem>
                  ))}
                </Menu>

                <Button sx={{ color: '#A1A1AA', textTransform: 'none', fontWeight: 500, '&:hover': { color: '#FFF' } }} onClick={() => navigate('/login')}>
                  {t('landing.nav.login')}
                </Button>
                <Button variant="contained" sx={{ borderRadius: '8px', px: 2, bgcolor: '#FFF', color: '#000', textTransform: 'none', fontWeight: 600, '&:hover': { bgcolor: '#E4E4E7' } }} onClick={() => navigate('/register')}>
                  {t('landing.nav.start')}
                </Button>
              </Stack>
            )}

            {/* Mobile Menu Icon */}
            {isMobile && (
              <IconButton onClick={() => setMobileMenuOpen(true)} sx={{ color: '#FFF' }}><MenuIcon /></IconButton>
            )}
          </Toolbar>
        </Container>
      </AppBar>

      {/* Mobile Drawer */}
      <Drawer anchor={isRtl ? 'left' : 'right'} open={mobileMenuOpen} onClose={() => setMobileMenuOpen(false)} PaperProps={{ sx: { bgcolor: '#0A0A0A', width: 260, color: '#FFF' } }}>
        <List sx={{ pt: 10, px: 2 }}>
          <ListItem component="button" onClick={() => scrollToSection('features')} sx={{ color: '#FFF' }}><ListItemText primary={t('landing.nav.features')} /></ListItem>
          <ListItem component="button" onClick={() => scrollToSection('pricing')} sx={{ color: '#FFF' }}><ListItemText primary={t('landing.nav.pricing')} /></ListItem>
          <Divider sx={{ my: 2, bgcolor: 'rgba(255,255,255,0.1)' }} />
          <ListItem component="button" onClick={() => navigate('/login')} sx={{ color: '#FFF' }}><ListItemText primary={t('landing.nav.login')} /></ListItem>
          <ListItem><Button fullWidth variant="contained" sx={{ bgcolor: '#FFF', color: '#000' }} onClick={() => navigate('/register')}>{t('landing.nav.start')}</Button></ListItem>
        </List>
      </Drawer>

      {/* --- HERO --- */}
      <Box sx={{ pt: { xs: 15, md: 20 }, pb: '64px', minHeight: '70vh', display: 'flex', alignItems: 'center' }}>
        <Container maxWidth="lg">
          <Grid container spacing={8} alignItems="center" direction={isRtl ? 'row-reverse' : 'row'}>
            <Grid item xs={12} md={6}>
              <motion.div initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.1 } } }}>
                <motion.div variants={fadeIn}>
                  <Chip label={t('landing.hero.badge')} sx={{ bgcolor: 'rgba(255,255,255,0.05)', color: '#D4D4D8', fontWeight: 600, mb: 3, borderRadius: '8px', fontSize: '0.75rem' }} />
                </motion.div>
                <motion.div variants={fadeIn}>
                  <Typography variant="h1" sx={{ fontSize: { xs: '2rem', md: '3rem' }, fontWeight: 800, mb: 2, lineHeight: 1.2, letterSpacing: '-0.02em' }} dangerouslySetInnerHTML={{ __html: t('landing.hero.title') }} />
                </motion.div>
                <motion.div variants={fadeIn}>
                  <Typography variant="body1" sx={{ color: '#A1A1AA', mb: 5, fontSize: '1.125rem', lineHeight: 1.5, maxWidth: 480 }}>
                    {t('landing.hero.subtitle')}
                  </Typography>
                </motion.div>
                <motion.div variants={fadeIn}>
                  <Stack direction="row" spacing={2}>
                    <Button variant="contained" size="large" sx={{ bgcolor: '#FFF', color: '#000', borderRadius: '10px', px: 4, fontWeight: 700, textTransform: 'none' }} onClick={() => navigate('/register')}>{t('landing.hero.cta_primary')}</Button>
                    <Button variant="outlined" size="large" sx={{ color: '#FFF', borderColor: 'rgba(255,255,255,0.15)', borderRadius: '10px', px: 4, fontWeight: 600, textTransform: 'none' }}>{t('landing.hero.cta_secondary')}</Button>
                  </Stack>
                </motion.div>
              </motion.div>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box sx={{ p: 1, borderRadius: '24px', bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', boxShadow: '0 40px 100px rgba(0,0,0,0.5)' }}>
                <Box component="img" src="/assets/landing/Automated_Meeting.png" sx={{ width: '100%', borderRadius: '16px', display: 'block' }} alt="SaaS Hub" />
              </Box>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* --- FEATURES --- */}
      <Box id="features" sx={{ py: '80px' }}>
        <Container maxWidth="lg">
          <Typography variant="h2" fontWeight="800" textAlign="center" sx={{ mb: 8, fontSize: '2rem', letterSpacing: '-0.02em' }}>{t('landing.features.title')}</Typography>
          <Grid container spacing={4}>
            {[
              { img: 'security.png', title: t('landing.features.security_title'), desc: t('landing.features.security_desc'), icon: <ShieldIcon /> },
              { img: 'diarization.png', title: t('landing.features.diarization_title'), desc: t('landing.features.diarization_desc'), icon: <VoiceIcon /> },
              { img: 'maghreb.png', title: t('landing.features.maghreb_title'), desc: t('landing.features.maghreb_desc'), icon: <GlobalIcon /> },
              { img: 'automation.png', title: t('landing.features.automation_title'), desc: t('landing.features.automation_desc'), icon: <WhatsAppIcon /> }
            ].map((f, i) => (
              <Grid item xs={12} md={6} key={i}>
                <Box className="glass-card" sx={{ p: 4, height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
                    <Avatar sx={{ bgcolor: 'rgba(255,255,255,0.05)', color: '#FFF', width: 44, height: 44 }}>{f.icon}</Avatar>
                    <Typography variant="h6" fontWeight="700" sx={{ fontSize: '1.125rem' }}>{f.title}</Typography>
                  </Stack>
                  <Typography variant="body2" sx={{ color: '#A1A1AA', lineHeight: 1.5, mb: 4, height: 48, overflow: 'hidden' }}>{f.desc}</Typography>
                  <Box sx={{ mt: 'auto', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <Box component="img" src={`/assets/landing/${f.img}`} sx={{ width: '100%', height: 180, objectFit: 'cover', opacity: 0.8 }} />
                  </Box>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* --- PIPELINE --- */}
      <Box sx={{ py: '80px', borderTop: '1px solid rgba(255,255,255,0.05)', bgcolor: 'rgba(255,255,255,0.01)' }}>
        <Container maxWidth="lg">
          <Typography variant="h3" fontWeight="800" textAlign="center" sx={{ mb: 2, fontSize: '1.75rem' }}>{t('landing.pipeline.title')}</Typography>
          <Typography variant="body2" textAlign="center" sx={{ color: '#71717A', mb: 8 }}>{t('landing.pipeline.subtitle')}</Typography>
          
          <Grid container spacing={3} justifyContent="center">
            {[
              { icon: <VoiceIcon />, text: t('landing.pipeline.step1') },
              { icon: <ChipIcon />, text: t('landing.pipeline.step2') },
              { icon: <EditIcon />, text: t('landing.pipeline.step3') },
              { icon: <WhatsAppIcon />, text: t('landing.pipeline.step4') }
            ].map((s, i) => (
              <Grid item xs={6} md={2.5} key={i}>
                <Box sx={{ textAlign: 'center' }}>
                  <Box sx={{ width: 48, height: 48, borderRadius: '14px', bgcolor: 'rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center', mx: 'auto', mb: 2, border: '1px solid rgba(255,255,255,0.08)' }}>{s.icon}</Box>
                  <Typography variant="body2" fontWeight="700">{s.text}</Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* --- PRICING --- */}
      <Box id="pricing" sx={{ py: '80px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
        <Container maxWidth="lg">
          <Typography variant="h3" fontWeight="800" textAlign="center" sx={{ mb: 8, fontSize: '2rem' }}>{t('landing.pricing.title')}</Typography>
          <Grid container spacing={4} justifyContent="center">
            {[
              { name: t('landing.pricing.free_name'), price: "0", feats: t('landing.pricing.starter_feats', { returnObjects: true }) as string[], h: false },
              { name: t('landing.pricing.pro_name'), price: "99", feats: t('landing.pricing.pro_feats', { returnObjects: true }) as string[], h: true },
              { name: t('landing.pricing.ent_name'), price: "499", feats: t('landing.pricing.ent_feats', { returnObjects: true }) as string[], h: false }
            ].map((p, i) => (
              <Grid item xs={12} md={4} key={i}>
                <Box className="glass-card" sx={{ p: 5, height: '100%', display: 'flex', flexDirection: 'column', borderColor: p.h ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.06)' }}>
                  <Typography variant="h6" fontWeight="700" sx={{ mb: 1 }}>{p.name}</Typography>
                  <Typography variant="h3" fontWeight="800" sx={{ mb: 4 }}>${p.price}<Box component="span" sx={{ fontSize: '1rem', color: '#71717A', ml: 1 }}>/{t('landing.pricing.monthly')}</Box></Typography>
                  <Stack spacing={2} sx={{ mb: 6, flexGrow: 1 }}>
                    {p.feats.map((feat, j) => (
                      <Stack direction="row" spacing={2} key={j} alignItems="center">
                        <CheckIcon sx={{ fontSize: 16, color: '#71717A' }} />
                        <Typography variant="body2" sx={{ color: '#A1A1AA' }}>{feat}</Typography>
                      </Stack>
                    ))}
                  </Stack>
                  <Button fullWidth variant={p.h ? "contained" : "outlined"} sx={{ py: 1.5, borderRadius: '10px', textTransform: 'none', fontWeight: 700, bgcolor: p.h ? '#FFF' : 'transparent', color: p.h ? '#000' : '#FFF' }}>{t('landing.nav.start')}</Button>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* --- FOOTER --- */}
      <Box sx={{ py: 6, borderTop: '1px solid rgba(255,255,255,0.08)', bgcolor: '#000' }}>
        <Container maxWidth="lg">
          <Stack direction={{xs: 'column', md: 'row'}} justifyContent="space-between" alignItems="center" spacing={4}>
            <Box textAlign={{xs: 'center', md: 'left'}}>
              <Typography variant="subtitle1" fontWeight="700" sx={{ mb: 1 }}>MeetingAutomation</Typography>
              <Typography variant="body2" sx={{ color: '#52525B' }}>{t('landing.footer.copyright')}</Typography>
            </Box>
            <Stack direction="row" spacing={4}>
              <MuiLink href="#" sx={{ color: '#71717A', textDecoration: 'none', fontSize: '0.875rem' }}>{t('landing.footer.privacy')}</MuiLink>
              <MuiLink href="#" sx={{ color: '#71717A', textDecoration: 'none', fontSize: '0.875rem' }}>{t('landing.footer.terms')}</MuiLink>
            </Stack>
          </Stack>
        </Container>
      </Box>
    </Box>
  );
};

export default LandingPage;