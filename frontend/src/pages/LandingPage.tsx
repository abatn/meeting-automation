import React, { useState, useEffect, useRef } from 'react';
import { 
  Box, Container, Typography, Button, Grid, Stack,
  AppBar, Toolbar, Link as MuiLink, Divider,
  Menu, MenuItem, CssBaseline, Chip, Avatar,
  IconButton, useTheme, useMediaQuery, Drawer, List, ListItem, ListItemText,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  Snackbar, Alert
} from '@mui/material';
import { 
  AutoFixHigh as IAIcon, GraphicEq as VoiceIcon,
  CheckCircle as CheckIcon, Security as ShieldIcon, 
  WhatsApp as WhatsAppIcon, Public as GlobalIcon,
  Description as EditIcon, Translate as TranslateIcon, 
  Memory as ChipIcon, Menu as MenuIcon,
  Mail as MailIcon, Phone as PhoneIcon
} from '@mui/icons-material';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import cmsService from '../services/cms';
import api from '../services/api';

const fadeIn = {
  hidden: { opacity: 0, y: 15 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" as const } }
} as const;

const LandingPage: React.FC = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const theme = useTheme();
  const isRtl = i18n.dir() === 'rtl';
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isSmallMobile = useMediaQuery('(max-width:360px)');

  const [anchorElLang, setAnchorElLang] = useState<null | HTMLElement>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [contactOpen, setContactOpen] = useState(false);
  const [videoOpen, setVideoOpen] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const handleVideoClose = () => {
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }
    setVideoOpen(false);
  };
  const [contactForm, setContactForm] = useState({ name: '', email: '', message: '' });
  const [contactSending, setContactSending] = useState(false);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMsg, setSnackbarMsg] = useState('');
  const [pricingPlans, setPricingPlans] = useState<Record<string, { price: number; minutes: number | null }>>({
    GRATUIT: { price: 0, minutes: 15 },
    PRO: { price: 199, minutes: 1800 },
    ENTREPRISE: { price: 399, minutes: 3600 },
  });

  const handleOpenLangMenu = (event: React.MouseEvent<HTMLElement>) => setAnchorElLang(event.currentTarget);
  const handleCloseLangMenu = () => setAnchorElLang(null);
  
  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    handleCloseLangMenu();
    setMobileMenuOpen(false);
  };

  const handleContactSend = async () => {
    setContactSending(true);
    try {
      await api.post('/contact', contactForm);
      setSnackbarMsg(i18n.language.startsWith('ar') ? 'تم الإرسال بنجاح!' : i18n.language.startsWith('fr') ? 'Envoyé avec succès !' : 'Message sent successfully!');
      setSnackbarOpen(true);
      setContactOpen(false);
      setContactForm({ name: '', email: '', message: '' });
    } catch {
      setSnackbarMsg(i18n.language.startsWith('ar') ? 'فشل الإرسال' : i18n.language.startsWith('fr') ? "Échec de l'envoi" : 'Failed to send. Please try again.');
      setSnackbarOpen(true);
    } finally {
      setContactSending(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setSnackbarMsg(i18n.language.startsWith('ar') ? 'تم النسخ!' : i18n.language.startsWith('fr') ? 'Copié !' : 'Copied!');
      setSnackbarOpen(true);
    });
  };

  // Fetch pricing from CMS API
  useEffect(() => {
    const fetchPricing = async () => {
      try {
        const plans = await cmsService.getPricing(i18n.language);
        const planMap: Record<string, { price: number; minutes: number | null }> = {
          GRATUIT: { price: 0, minutes: 15 },
          PRO: { price: 199, minutes: 1800 },
          ENTREPRISE: { price: 399, minutes: 3600 },
        };
        plans.forEach((plan: any) => {
          if (plan.plan_code) {
            planMap[plan.plan_code] = {
              price: plan.price_monthly ?? planMap[plan.plan_code]?.price ?? 0,
              minutes: plan.minutes_included ?? null,
            };
          }
        });
        setPricingPlans(planMap);
      } catch (err) {
        console.warn('Failed to fetch CMS pricing, using defaults');
      }
    };
    fetchPricing();
  }, [i18n.language]);

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      const offset = isMobile ? 70 : 90;
      window.scrollTo({ top: element.getBoundingClientRect().top + window.scrollY - offset, behavior: 'smooth' });
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
      overflowX: 'hidden',
      fontFamily: isRtl ? "'Noto Sans Arabic', sans-serif" : "'Inter', sans-serif"
    }}>
      <CssBaseline />
      
      <style>
        {`
          .glass-card {
            background: rgba(255, 255, 255, 0.02);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 24px;
            height: 100%;
            display: flex;
            flex-direction: column;
          }

          @media (hover: hover) {
            .glass-card:hover {
              background: rgba(255, 255, 255, 0.04);
              border-color: rgba(255, 255, 255, 0.12);
              transform: translateY(-6px);
              box-shadow: 0 20px 40px rgba(0,0,0,0.3);
              transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
          }
        `}
      </style>

      {/* --- NAVIGATION --- */}
      <AppBar position="fixed" elevation={0} sx={{ bgcolor: 'rgba(5, 5, 5, 0.85)', backdropFilter: 'blur(16px)', borderBottom: '1px solid rgba(255,255,255,0.06)', zIndex: 1201 }}>
        <Container maxWidth="lg">
          <Toolbar disableGutters sx={{ justifyContent: 'space-between', height: { xs: 64, md: 80 } }}>
            <Stack direction="row" alignItems="center" sx={{ cursor: 'pointer' }} onClick={() => window.scrollTo({top: 0, behavior: 'smooth'})}>
              <Box sx={{ width: { xs: 28, md: 32 }, height: { xs: 28, md: 32 }, bgcolor: '#FFF', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', mx: 1.5 }}>
                <IAIcon sx={{ color: '#000', fontSize: { xs: 16, md: 20 } }} />
              </Box>
              <Typography variant="h6" fontWeight="700" sx={{ letterSpacing: '-0.5px', color: 'white', fontSize: { xs: '1rem', md: '1.25rem' } }}>
                {t('common.appNamePart1')} <Box component="span" sx={{ color: '#71717A' }}>{t('common.appNamePart2')}</Box>
              </Typography>
            </Stack>

            {!isMobile ? (
              <Stack direction="row" sx={{ gap: 3 }} alignItems="center">
                <MuiLink component="button" onClick={() => scrollToSection('features')} sx={{ color: '#A1A1AA', textDecoration: 'none', fontWeight: 500, '&:hover': { color: '#FFF' } }}>{t('landing.nav.features')}</MuiLink>
                <MuiLink component="button" onClick={() => scrollToSection('pricing')} sx={{ color: '#A1A1AA', textDecoration: 'none', fontWeight: 500, '&:hover': { color: '#FFF' } }}>{t('landing.nav.pricing')}</MuiLink>
                <MuiLink component="button" onClick={() => setContactOpen(true)} sx={{ color: '#A1A1AA', textDecoration: 'none', fontWeight: 500, '&:hover': { color: '#FFF' } }}>{t('landing.nav.contact')}</MuiLink>
                <Divider orientation="vertical" flexItem sx={{ borderColor: 'rgba(255,255,255,0.1)', height: 20 }} />
                <Button onClick={handleOpenLangMenu} startIcon={<TranslateIcon sx={{fontSize: 18}} />} sx={{ color: '#A1A1AA', textTransform: 'none', fontWeight: 600 }}>
                  {i18n.language.split('-')[0].toUpperCase()}
                </Button>
                <Button sx={{ color: '#A1A1AA', textTransform: 'none', fontWeight: 500, '&:hover': { color: '#FFF' } }} onClick={() => navigate('/login')}>
                  {t('landing.nav.login')}
                </Button>
                <Button variant="contained" sx={{ borderRadius: '10px', px: 3, bgcolor: '#FFF', color: '#000', textTransform: 'none', fontWeight: 700, '&:hover': { bgcolor: '#E4E4E7' } }} onClick={() => navigate('/register')}>
                  {t('landing.nav.start')}
                </Button>
              </Stack>
            ) : (
              <IconButton onClick={() => setMobileMenuOpen(true)} sx={{ color: '#FFF', p: 1.5 }} aria-label="menu">
                <MenuIcon fontSize="large" />
              </IconButton>
            )}
          </Toolbar>
        </Container>
      </AppBar>

      <Menu 
        anchorEl={anchorElLang} 
        open={Boolean(anchorElLang)} 
        onClose={handleCloseLangMenu}
        PaperProps={{ sx: { bgcolor: '#18181B', color: '#FFF', border: '1px solid rgba(255,255,255,0.1)', minWidth: 140 } }}
      >
        {languages.map((l) => (
          <MenuItem key={l.code} onClick={() => changeLanguage(l.code)} sx={{ fontSize: '14px', py: 1.5, fontWeight: i18n.language === l.code ? 700 : 400 }}>
            {l.label}
          </MenuItem>
        ))}
      </Menu>

      {/* --- MOBILE DRAWER --- */}
      <Drawer 
        anchor={isRtl ? 'left' : 'right'} 
        open={mobileMenuOpen} 
        onClose={() => setMobileMenuOpen(false)} 
        PaperProps={{ sx: { bgcolor: '#0A0A0A', width: '85%', maxWidth: 320, color: '#FFF' } }}
      >
        <Box sx={{ p: 4 }}>
          <Typography variant="h6" fontWeight="800" sx={{ mb: 4, letterSpacing: '-0.5px' }}>{t('common.appNamePart1')}{t('common.appNamePart2')}</Typography>
          <List>
            {['features', 'pricing'].map((item) => (
              <ListItem key={item} disablePadding sx={{ mb: 2 }}>
                <Button fullWidth onClick={() => scrollToSection(item)} sx={{ justifyContent: isRtl ? 'flex-end' : 'flex-start', color: '#A1A1AA', fontSize: '1.1rem', py: 1.5, textTransform: 'none' }}>
                  {t(`landing.nav.${item}`)}
                </Button>
              </ListItem>
            ))}
            <ListItem disablePadding sx={{ mb: 2 }}>
              <Button fullWidth onClick={() => { setContactOpen(true); setMobileMenuOpen(false); }} sx={{ justifyContent: isRtl ? 'flex-end' : 'flex-start', color: '#A1A1AA', fontSize: '1.1rem', py: 1.5, textTransform: 'none' }}>
                {t('landing.nav.contact')}
              </Button>
            </ListItem>
            <Divider sx={{ my: 3, bgcolor: 'rgba(255,255,255,0.1)' }} />
            <Typography variant="caption" sx={{ color: '#71717A', mb: 2, display: 'block', textTransform: 'uppercase' }}>{t('common.toggleLanguage')}</Typography>
            <Grid container spacing={1} sx={{ mb: 4 }}>
              {languages.map((l) => (
                <Grid item xs={4} key={l.code}>
                  <Button 
                    fullWidth 
                    variant={i18n.language === l.code ? "contained" : "outlined"}
                    onClick={() => changeLanguage(l.code)}
                    sx={{ 
                      fontSize: '0.7rem', 
                      px: 0, 
                      bgcolor: i18n.language === l.code ? '#FFF' : 'transparent',
                      color: i18n.language === l.code ? '#000' : '#FFF',
                      borderColor: 'rgba(255,255,255,0.2)'
                    }}
                  >
                    {l.code.split('-')[0].toUpperCase()}
                  </Button>
                </Grid>
              ))}
            </Grid>
            <ListItem disablePadding sx={{ mb: 2 }}>
              <Button fullWidth onClick={() => { setVideoOpen(true); setMobileMenuOpen(false); }} sx={{ justifyContent: isRtl ? 'flex-end' : 'flex-start', color: '#A1A1AA', fontSize: '1.1rem', py: 1.5, textTransform: 'none' }}>
                {t('landing.hero.cta_secondary')}
              </Button>
            </ListItem>
            <ListItem disablePadding sx={{ mb: 2 }}>
              <Button fullWidth onClick={() => navigate('/login')} sx={{ justifyContent: isRtl ? 'flex-end' : 'flex-start', color: '#FFF', fontSize: '1.1rem', py: 1.5, textTransform: 'none' }}>
                {t('landing.nav.login')}
              </Button>
            </ListItem>
            <Button fullWidth variant="contained" size="large" sx={{ bgcolor: '#FFF', color: '#000', py: 2, borderRadius: '12px', fontWeight: 800 }} onClick={() => navigate('/register')}>
              {t('landing.nav.start')}
            </Button>
          </List>
        </Box>
      </Drawer>

      {/* --- HERO --- */}
      <Box sx={{ pt: { xs: 12, md: 22 }, pb: { xs: 8, md: 12 }, overflow: 'hidden' }}>
        <Container maxWidth="lg">
          <Grid container spacing={{ xs: 6, md: 10 }} alignItems="center">
            <Grid item xs={12} md={6}>
              <motion.div initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.12 } } }}>
                <motion.div variants={fadeIn}>
                  <Chip label={t('landing.hero.version_badge')} sx={{ bgcolor: 'rgba(255,255,255,0.06)', color: '#FFF', fontWeight: 700, mb: 3, borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }} />
                </motion.div>
                <motion.div variants={fadeIn}>
                  <Typography variant="h1" sx={{ 
                    fontSize: { xs: isSmallMobile ? '1.85rem' : '2.25rem', sm: '3rem', md: '4rem' }, 
                    fontWeight: 800, mb: 2.5, lineHeight: 1.1, letterSpacing: '-0.03em' 
                  }}>
                    {t('landing.hero.title').split('<br/>').map((line, i, arr) => (
                      <React.Fragment key={i}>
                        {line}
                        {i < arr.length - 1 && <br />}
                      </React.Fragment>
                    ))}
                  </Typography>
                </motion.div>
                <motion.div variants={fadeIn}>
                  <Typography variant="body1" sx={{ color: '#A1A1AA', mb: 5, fontSize: { xs: '1.05rem', md: '1.25rem' }, lineHeight: 1.6, maxWidth: 540 }}>
                    {t('landing.hero.subtitle')}
                  </Typography>
                </motion.div>
                <motion.div variants={fadeIn}>
                  <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
                    <Button variant="contained" size="large" sx={{ bgcolor: '#FFF', color: '#000', borderRadius: '12px', py: { xs: 2, md: 2.5 }, px: 4, fontWeight: 800, textTransform: 'none', fontSize: '1.1rem' }} onClick={() => navigate('/register')}>{t('landing.hero.cta_primary')}</Button>
                    <Button variant="outlined" size="large" sx={{ color: '#FFF', borderColor: 'rgba(255,255,255,0.2)', borderRadius: '12px', py: { xs: 2, md: 2.5 }, px: 4, fontWeight: 700, textTransform: 'none', fontSize: '1.1rem' }} onClick={() => setVideoOpen(true)}>{t('landing.hero.cta_secondary')}</Button>
                  </Stack>
                </motion.div>
              </motion.div>
            </Grid>
            <Grid item xs={12} md={6}>
                <Box sx={{ position: 'relative', p: { xs: 0.5, md: 1.5 }, borderRadius: '32px', bgcolor: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 30px 90px rgba(0,0,0,0.6)' }}>
                  <Box component="img" src="/assets/landing/Automated_Meeting.png" sx={{ width: '100%', height: 'auto', borderRadius: '24px', display: 'block', maxWidth: '100%' }} alt={t('landing.hero.alt_dashboard')} loading="eager" />
                </Box>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* --- TRUST --- */}
      <Box sx={{ py: 6, borderY: '1px solid rgba(255,255,255,0.06)', bgcolor: 'rgba(255,255,255,0.01)' }}>
        <Container maxWidth="lg">
          <Stack direction={{xs: 'column', md: 'row'}} sx={{ gap: { xs: 3, md: 6 } }} alignItems="center" justifyContent="center">
            <Typography variant="caption" sx={{ color: '#71717A', fontWeight: 800, letterSpacing: '0.15em', textTransform: 'uppercase' }}>
              {t('landing.trust.title')}
            </Typography>
            <Stack direction="row" sx={{ gap: 3 }} flexWrap="wrap" justifyContent="center">
               {['iso', 'aes', 'gdpr'].map(item => (
                 <Chip key={item} label={t(`landing.trust.${item}`)} size="small" variant="outlined" sx={{ color: '#A1A1AA', borderColor: 'rgba(255,255,255,0.12)', py: 2, px: 1 }} />
               ))}
            </Stack>
          </Stack>
        </Container>
      </Box>

      {/* --- FEATURES --- */}
      <Box id="features" sx={{ py: { xs: 8, md: 14 } }}>
        <Container maxWidth="lg">
          <Typography variant="h2" fontWeight="800" textAlign="center" sx={{ mb: { xs: 6, md: 10 }, fontSize: { xs: '2rem', md: '3rem' }, letterSpacing: '-0.02em' }}>{t('landing.features.title')}</Typography>
          <Grid container spacing={3}>
            {[
              { img: 'security.png', title: t('landing.features.security_title'), desc: t('landing.features.security_desc'), icon: <ShieldIcon />, alt: t('landing.features.security_title') },
              { img: 'diarization.png', title: t('landing.features.diarization_title'), desc: t('landing.features.diarization_desc'), icon: <VoiceIcon />, alt: t('landing.features.diarization_title') },
              { img: 'maghreb.png', title: t('landing.features.maghreb_title'), desc: t('landing.features.maghreb_desc'), icon: <GlobalIcon />, alt: t('landing.features.maghreb_title') },
              { img: 'automation.png', title: t('landing.features.automation_title'), desc: t('landing.features.automation_desc'), icon: <WhatsAppIcon />, alt: t('landing.features.automation_title') }
            ].map((f, i) => (
              <Grid item xs={12} sm={6} key={i}>
                <Box className="glass-card" sx={{ p: { xs: 3, md: 5 } }}>
                  <Stack direction="row" sx={{ gap: 2, mb: 3 }} alignItems="center">
                    <Avatar sx={{ bgcolor: 'rgba(255,255,255,0.06)', color: '#FFF', width: 48, height: 48, border: '1px solid rgba(255,255,255,0.1)' }}>{f.icon}</Avatar>
                    <Typography variant="h6" fontWeight="700" sx={{ fontSize: '1.2rem' }}>{f.title}</Typography>
                  </Stack>
                  <Typography variant="body2" sx={{ color: '#A1A1AA', lineHeight: 1.6, mb: 4, flexGrow: 1, fontSize: '1rem' }}>{f.desc}</Typography>
                  <Box sx={{ mt: 'auto', borderRadius: '16px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)' }}>
                    <Box component="img" src={`/assets/landing/${f.img}`} sx={{ width: '100%', height: { xs: 200, md: 240 }, objectFit: 'cover', opacity: 0.9 }} alt={f.alt} loading="lazy" />
                  </Box>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* --- PIPELINE --- */}
      <Box sx={{ py: { xs: 8, md: 14 }, borderTop: '1px solid rgba(255,255,255,0.06)', bgcolor: 'rgba(255,255,255,0.01)' }}>
        <Container maxWidth="lg">
          <Typography variant="h3" fontWeight="800" textAlign="center" sx={{ mb: 2, fontSize: { xs: '1.75rem', md: '2.25rem' } }}>
            {t('landing.pipeline.title')}
          </Typography>
          <Typography variant="body2" textAlign="center" sx={{ color: '#71717A', mb: { xs: 6, md: 10 }, fontSize: '1rem' }}>
            {t('landing.pipeline.subtitle')}
          </Typography>
          
          <Grid container spacing={{ xs: 4, md: 3 }} justifyContent="center">
            {[
              { icon: <VoiceIcon />, textKey: 'landing.pipeline.step1' },
              { icon: <ChipIcon />, textKey: 'landing.pipeline.step2' },
              { icon: <EditIcon />, textKey: 'landing.pipeline.step3' },
              { icon: <WhatsAppIcon />, textKey: 'landing.pipeline.step4' }
            ].map((s, i) => (
              <Grid item xs={6} md={3} key={i}>
                <Box sx={{ textAlign: 'center' }}>
                  <Box sx={{ 
                    width: { xs: 56, md: 64 }, 
                    height: { xs: 56, md: 64 }, 
                    borderRadius: '18px', 
                    bgcolor: 'rgba(255,255,255,0.03)', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center', 
                    mx: 'auto', 
                    mb: 2.5, 
                    border: '1px solid rgba(255,255,255,0.08)',
                    color: '#FFF'
                  }}>
                    {React.cloneElement(s.icon as React.ReactElement, { sx: { fontSize: { xs: 28, md: 32 } } })}
                  </Box>
                  <Typography variant="body2" fontWeight="700" sx={{ color: '#FFF', fontSize: { xs: '0.9rem', md: '1rem' } }}>
                    {t(s.textKey)}
                  </Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* --- PRICING --- */}
      <Box id="pricing" sx={{ py: { xs: 8, md: 14 }, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        <Container maxWidth="lg">
          <Typography variant="h2" fontWeight="800" textAlign="center" sx={{ mb: { xs: 6, md: 10 }, fontSize: { xs: '2rem', md: '3rem' } }}>{t('landing.pricing.title')}</Typography>
          <Grid container spacing={4} justifyContent="center">
            {[
              { nameKey: 'landing.pricing.free_name', planCode: 'GRATUIT', featsKey: 'landing.pricing.starter_feats', h: false },
              { nameKey: 'landing.pricing.pro_name', planCode: 'PRO', featsKey: 'landing.pricing.pro_feats', h: true },
              { nameKey: 'landing.pricing.ent_name', planCode: 'ENTREPRISE', featsKey: 'landing.pricing.ent_feats', h: false }
            ].map((p, i) => {
              const plan = pricingPlans[p.planCode] || { price: 0, minutes: null };
              return (
              <Grid item xs={12} md={4} key={i}>
                <Box className="glass-card" sx={{ p: { xs: 4, md: 6 }, border: p.h ? '1px solid rgba(255,255,255,0.2)' : '1px solid rgba(255,255,255,0.05)', position: 'relative' }}>
                  {p.h && <Chip label={t('landing.pricing.popular_badge')} size="small" sx={{ position: 'absolute', top: 20, right: 20, bgcolor: '#FFF', color: '#000', fontWeight: 900, borderRadius: '4px' }} />}
                  <Typography variant="h6" fontWeight="800" sx={{ mb: 1, color: p.h ? '#FFF' : '#71717A' }}>{t(p.nameKey)}</Typography>
                  <Stack direction="row" alignItems="baseline" sx={{ gap: 1, mb: 1 }}>
                    <Typography variant="h3" fontWeight={800}>{plan.price} TND</Typography>
                    <Typography variant="body2" sx={{ color: '#71717A' }}>/{t('landing.pricing.monthly')}</Typography>
                  </Stack>
                  {plan.minutes != null && (
                    <Typography variant="body2" sx={{ color: '#A1A1AA', mb: 4, fontWeight: 600 }}>
                      {t('landing.pricing.minutes_label', { count: plan.minutes })}
                    </Typography>
                  )}
                  <Stack sx={{ gap: 2, mb: 6, flexGrow: 1 }}>
                    {(t(p.featsKey, { returnObjects: true }) as string[]).map((feat, j) => (
                      <Stack direction="row" sx={{ gap: 1.5 }} key={j} alignItems="center">
                        <CheckIcon sx={{ fontSize: 18, color: '#22C55E' }} />
                        <Typography variant="body2" sx={{ color: '#A1A1AA', fontSize: '0.95rem' }}>{feat}</Typography>
                      </Stack>
                    ))}
                  </Stack>
                  <Button fullWidth variant={p.h ? "contained" : "outlined"} sx={{ py: 2, borderRadius: '12px', fontWeight: 800, bgcolor: p.h ? '#FFF' : 'transparent', color: p.h ? '#000' : '#FFF', border: p.h ? 'none' : '1px solid rgba(255,255,255,0.2)' }} onClick={() => navigate(`/register?plan=${p.planCode}`)}>{[t('landing.pricing.start_free'), t('landing.pricing.start_pro'), t('landing.pricing.start_enterprise')][i]}</Button>
                </Box>
              </Grid>
              );
            })}
          </Grid>
        </Container>
      </Box>

      {/* --- FOOTER --- */}
      <Box sx={{ py: { xs: 6, md: 8 }, borderTop: '1px solid rgba(255,255,255,0.08)', bgcolor: '#000' }}>
        <Container maxWidth="lg">
          <Stack direction={{xs: 'column', md: 'row'}} justifyContent="space-between" alignItems="center" sx={{ gap: 4 }}>
            <Box textAlign={{xs: 'center', md: isRtl ? 'right' : 'left'}}>
              <Typography variant="h6" fontWeight="800" sx={{ mb: 1 }}>{t('common.appNamePart1')}{t('common.appNamePart2')}</Typography>
              <Typography variant="body2" sx={{ color: '#52525B' }}>{t('landing.footer.copyright')}</Typography>
            </Box>
            <Stack direction="row" sx={{ gap: 4 }}>
              <MuiLink component={RouterLink} to="/privacy" sx={{ color: '#71717A', textDecoration: 'none', fontSize: '0.9rem', '&:hover': { color: '#A1A1AA' } }}>{t('landing.footer.privacy')}</MuiLink>
              <MuiLink component={RouterLink} to="/terms" sx={{ color: '#71717A', textDecoration: 'none', fontSize: '0.9rem', '&:hover': { color: '#A1A1AA' } }}>{t('landing.footer.terms')}</MuiLink>
              <MuiLink component="button" onClick={() => setContactOpen(true)} sx={{ color: '#71717A', textDecoration: 'none', fontSize: '0.9rem', background: 'none', border: 'none', cursor: 'pointer', '&:hover': { color: '#A1A1AA' } }}>{t('landing.footer.contact')}</MuiLink>
            </Stack>
          </Stack>
        </Container>
      </Box>
      {/* --- VIDEO MODAL --- */}
      <Dialog
        open={videoOpen}
        onClose={handleVideoClose}
        maxWidth="md"
        fullWidth
        PaperProps={{ sx: { bgcolor: '#000', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '16px', overflow: 'hidden' } }}
      >
        <Box sx={{ position: 'relative', pt: '56.25%' /* 16:9 aspect ratio */ }}>
          <video
            ref={videoRef}
            controls
            autoPlay
            muted
            playsInline
            onEnded={handleVideoClose}
            style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'contain' }}
            src="/assets/landing/meeting_automation.MP4"
          />
        </Box>
      </Dialog>

      {/* --- CONTACT MODAL --- */}
      <Dialog 
        open={contactOpen} 
        onClose={() => setContactOpen(false)} 
        maxWidth="sm" 
        fullWidth
        PaperProps={{ sx: { bgcolor: '#18181B', color: '#FAFAFA', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '16px' } }}
      >
        <DialogTitle sx={{ fontWeight: 800, fontSize: '1.5rem', pb: 1 }}>{t('landing.contact.title')}</DialogTitle>
        <DialogContent dividers sx={{ borderColor: 'rgba(255,255,255,0.08)', pt: 3 }}>
          <Typography variant="body2" sx={{ color: '#A1A1AA', mb: 4 }}>{t('landing.contact.subtitle')}</Typography>
          
          <Stack spacing={3} sx={{ mb: 4 }}>
            <Stack direction="row" spacing={2} alignItems="center" sx={{ cursor: 'pointer', '&:hover .MuiAvatar-root': { bgcolor: 'rgba(255,255,255,0.12)' } }} onClick={() => copyToClipboard('contact@zedintek.com')}>
              <Avatar sx={{ bgcolor: 'rgba(255,255,255,0.06)', color: '#FFF', width: 40, height: 40, transition: 'bgcolor 0.2s' }}>
                <MailIcon sx={{ fontSize: 20 }} />
              </Avatar>
              <Box>
                <Typography variant="caption" sx={{ color: '#71717A', display: 'block' }}>{t('landing.contact.email_label')}</Typography>
                <Typography variant="body2" sx={{ color: '#FFF', fontSize: '0.95rem' }}>contact@zedintek.com</Typography>
              </Box>
            </Stack>
            <Stack direction="row" spacing={2} alignItems="center" sx={{ cursor: 'pointer', '&:hover .MuiAvatar-root': { bgcolor: 'rgba(255,255,255,0.12)' } }} onClick={() => copyToClipboard('+21652369325')}>
              <Avatar sx={{ bgcolor: 'rgba(255,255,255,0.06)', color: '#FFF', width: 40, height: 40, transition: 'bgcolor 0.2s' }}>
                <PhoneIcon sx={{ fontSize: 20 }} />
              </Avatar>
              <Box>
                <Typography variant="caption" sx={{ color: '#71717A', display: 'block' }}>{t('landing.contact.phone_label')}</Typography>
                <Typography variant="body2" sx={{ color: '#FFF', fontSize: '0.95rem', direction: 'ltr' }}>+216 52 369 325</Typography>
              </Box>
            </Stack>
          </Stack>

          <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)', mb: 4 }} />
          
          <Typography variant="body2" fontWeight="700" sx={{ mb: 2 }}>{t('landing.contact.message_section')}</Typography>
          <Stack spacing={2.5}>
            <TextField 
              fullWidth 
              size="small"
              label={t('landing.contact.name_label')}
              value={contactForm.name}
              onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
              sx={{ '& .MuiOutlinedInput-root': { color: '#FAFAFA', '& fieldset': { borderColor: 'rgba(255,255,255,0.15)' }, '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' } }, '& .MuiInputLabel-root': { color: '#71717A' } }}
            />
            <TextField 
              fullWidth 
              size="small"
              label={t('landing.contact.email_field')}
              type="email"
              value={contactForm.email}
              onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
              sx={{ '& .MuiOutlinedInput-root': { color: '#FAFAFA', '& fieldset': { borderColor: 'rgba(255,255,255,0.15)' }, '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' } }, '& .MuiInputLabel-root': { color: '#71717A' } }}
            />
            <TextField 
              fullWidth 
              multiline 
              rows={3}
              label={t('landing.contact.message_label')}
              value={contactForm.message}
              onChange={(e) => setContactForm({ ...contactForm, message: e.target.value })}
              sx={{ '& .MuiOutlinedInput-root': { color: '#FAFAFA', '& fieldset': { borderColor: 'rgba(255,255,255,0.15)' }, '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' } }, '& .MuiInputLabel-root': { color: '#71717A' } }}
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setContactOpen(false)} sx={{ color: '#71717A', textTransform: 'none' }}>{t('landing.contact.close')}</Button>
          <Button 
            variant="contained" 
            onClick={handleContactSend}
            disabled={!contactForm.name || !contactForm.email || !contactForm.message || contactSending}
            sx={{ bgcolor: '#FFF', color: '#000', textTransform: 'none', fontWeight: 700, borderRadius: '8px', px: 3, '&:hover': { bgcolor: '#E4E4E7' } }}
          >
            {contactSending ? '...' : t('landing.contact.send')}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbarOpen} autoHideDuration={3000} onClose={() => setSnackbarOpen(false)} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert onClose={() => setSnackbarOpen(false)} severity="success" sx={{ width: '100%', bgcolor: '#22C55E', color: '#FFF', '& .MuiAlert-icon': { color: '#FFF' } }}>
          {snackbarMsg}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default LandingPage;
