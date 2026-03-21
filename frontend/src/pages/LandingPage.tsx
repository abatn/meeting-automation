import React from 'react';
import { 
  Box, 
  Container, 
  Typography, 
  Button, 
  Grid, 
  Stack, 
  Divider,
  useTheme,
  AppBar,
  Toolbar,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Avatar,
  alpha
} from '@mui/material';
import { 
  AutoFixHigh as IAIcon, 
  AssignmentTurnedIn as ActionIcon, 
  RecordVoiceOver as VoiceIcon,
  CheckCircle as CheckIcon,
  ExpandMore as ExpandMoreIcon,
  Language as LangIcon,
  Security as ShieldIcon,
  TrendingUp as GrowthIcon,
  PlayArrow as PlayIcon
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();

  const handleStart = (plan?: string) => {
    if (plan) {
      navigate(`/register?plan=${plan}`);
    } else {
      navigate('/register');
    }
  };

  return (
    <Box sx={{ bgcolor: '#0B0F19', minHeight: '100vh', color: '#FFFFFF', overflow: 'hidden' }}>
      
      {/* --- BACKGROUND GLOW EFFECTS --- */}
      <Box sx={{ 
        position: 'absolute', top: -200, left: '10%', width: 600, height: 600, 
        background: `radial-gradient(circle, ${alpha(theme.palette.primary.main, 0.15)} 0%, rgba(0,0,0,0) 70%)`,
        filter: 'blur(80px)', zIndex: 0
      }} />
      <Box sx={{ 
        position: 'absolute', top: 400, right: '-5%', width: 500, height: 500, 
        background: `radial-gradient(circle, ${alpha(theme.palette.secondary.main, 0.1)} 0%, rgba(0,0,0,0) 70%)`,
        filter: 'blur(80px)', zIndex: 0
      }} />

      {/* --- NAVIGATION --- */}
      <AppBar 
        position="fixed" 
        elevation={0} 
        sx={{ 
          bgcolor: 'rgba(11, 15, 25, 0.7)', 
          backdropFilter: 'blur(15px)',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          zIndex: 10
        }}
      >
        <Container maxWidth="lg">
          <Toolbar disableGutters sx={{ justifyContent: 'space-between', height: 80 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
              <Box sx={{ 
                width: 40, height: 40, bgcolor: 'primary.main', borderRadius: '12px', 
                display: 'flex', alignItems: 'center', justifyContent: 'center', mr: 1.5,
                boxShadow: `0 0 20px ${alpha(theme.palette.primary.main, 0.5)}`
              }}>
                <IAIcon sx={{ color: 'white' }} />
              </Box>
              <Typography variant="h5" fontWeight="900" sx={{ letterSpacing: '-1px' }}>
                Meeting<Box component="span" sx={{ color: 'primary.main' }}>Automation</Box>
              </Typography>
            </Box>
            
            <Stack direction="row" spacing={3} alignItems="center">
              <Button color="inherit" sx={{ fontWeight: 600, textTransform: 'none', opacity: 0.8, '&:hover': { opacity: 1 } }} onClick={() => navigate('/login')}>
                Connexion
              </Button>
              <Button 
                variant="contained" 
                sx={{ 
                  borderRadius: '12px', px: 3, py: 1, fontWeight: 700, textTransform: 'none',
                  background: 'linear-gradient(90deg, #0070F3 0%, #00A3FF 100%)',
                  boxShadow: '0 8px 20px rgba(0,112,243,0.3)'
                }}
                onClick={() => handleStart()}
              >
                Commencer l'essai
              </Button>
            </Stack>
          </Toolbar>
        </Container>
      </AppBar>

      {/* --- HERO SECTION --- */}
      <Container maxWidth="lg" sx={{ pt: { xs: 20, md: 25 }, pb: 15, position: 'relative', zIndex: 1 }}>
        <Box sx={{ textAlign: 'center', mb: 10 }}>
          <Typography 
            variant="overline" 
            sx={{ 
              color: 'primary.main', fontWeight: 800, letterSpacing: 3, 
              border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.3),
              px: 2, py: 0.8, borderRadius: 10, bgcolor: alpha(theme.palette.primary.main, 0.05)
            }}
          >
            L'INTELLIGENCE ARTIFICIELLE AU SERVICE DU MAGHREB
          </Typography>
          <Typography 
            variant="h1" 
            sx={{ 
              fontSize: { xs: '3rem', md: '5rem' }, fontWeight: 900, mt: 4, mb: 3,
              lineHeight: 1, letterSpacing: '-2px',
              background: 'linear-gradient(to bottom, #FFFFFF 0%, #94A3B8 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
            }}
          >
            Générez vos PV de réunion <br/> <Box component="span" sx={{ color: '#0070F3' }}>en un clic</Box>
          </Typography>
          <Typography variant="h5" sx={{ color: '#94A3B8', mb: 6, maxWidth: 800, mx: 'auto', lineHeight: 1.6 }}>
            Transformez vos discussions en comptes-rendus professionnels, extrayez les actions clés et pilotez votre organisation avec une efficacité inégalée.
          </Typography>
          
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} justifyContent="center">
            <Button 
              variant="contained" 
              size="large" 
              sx={{ borderRadius: '14px', px: 6, py: 2.5, fontSize: '1.1rem', fontWeight: 800, textTransform: 'none', background: '#FFFFFF', color: '#000000', '&:hover': { background: '#E2E8F0' } }}
              onClick={() => handleStart('PRO')}
            >
              Démarrez gratuitement
            </Button>
            <Button 
              variant="outlined" 
              size="large" 
              startIcon={<PlayIcon />}
              sx={{ borderRadius: '14px', px: 6, py: 2.5, fontSize: '1.1rem', fontWeight: 800, textTransform: 'none', color: '#FFFFFF', borderColor: 'rgba(255,255,255,0.2)', borderWidth: 2 }}
            >
              Voir la démo
            </Button>
          </Stack>
        </Box>

        {/* --- MODERN DASHBOARD PREVIEW (MOCKUP) --- */}
        <Box sx={{ position: 'relative', width: '100%', maxWidth: 1100, mx: 'auto', perspective: '1500px' }}>
          <Paper 
            elevation={0}
            sx={{ 
              p: 1.5, borderRadius: '24px', bgcolor: 'rgba(255,255,255,0.03)', 
              border: '1px solid rgba(255,255,255,0.1)', backdropFilter: 'blur(10px)',
              transform: 'rotateX(5deg)', boxShadow: '0 50px 100px rgba(0,0,0,0.5)'
            }}
          >
            <Box sx={{ borderRadius: '18px', overflow: 'hidden', position: 'relative' }}>
              <Box component="img" 
                src="https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=80"
                sx={{ width: '100%', display: 'block', opacity: 0.9 }}
              />
              {/* Floating AI Status Tag */}
              <Paper sx={{ 
                position: 'absolute', top: '20%', left: '5%', p: 2, borderRadius: 3, 
                bgcolor: 'rgba(0,112,243,0.9)', color: 'white', display: 'flex', alignItems: 'center', gap: 1.5,
                boxShadow: '0 20px 40px rgba(0,0,0,0.3)', backdropFilter: 'blur(5px)'
              }}>
                <IAIcon />
                <Box>
                  <Typography variant="caption" fontWeight="bold">PV GENERATION</Typography>
                  <Typography variant="body2" fontWeight="800">Processing in 3.2s</Typography>
                </Box>
              </Paper>
            </Box>
          </Paper>
        </Box>
      </Container>

      {/* --- FEATURES GRID --- */}
      <Container maxWidth="lg" sx={{ py: 20, zIndex: 1, position: 'relative' }}>
        <Grid container spacing={4}>
          {[
            { icon: <VoiceIcon />, title: "Audio Multi-locuteurs", desc: "Identification précise des intervenants, même en cas de bruits de fond." },
            { icon: <IAIcon />, title: "Synthèse Intelligente", desc: "Résumé automatique des décisions, points bloquants et consensus." },
            { icon: <ActionIcon />, title: "Suivi des Actions", desc: "Extraction des tâches avec assignation et notifications automatiques." },
            { icon: <LangIcon />, title: "Dialectes Maghrébins", desc: "Support complet du Français et de l'Arabe (Tunisien, Darija)." }
          ].map((item, index) => (
            <Grid item xs={12} sm={6} md={3} key={index}>
              <Paper sx={{ 
                p: 4, height: '100%', bgcolor: 'rgba(255,255,255,0.02)', 
                border: '1px solid rgba(255,255,255,0.05)', borderRadius: 5,
                transition: '0.3s', '&:hover': { bgcolor: 'rgba(255,255,255,0.05)', borderColor: 'primary.main' }
              }}>
                <Avatar sx={{ bgcolor: alpha(theme.palette.primary.main, 0.15), color: 'primary.main', mb: 3 }}>
                  {item.icon}
                </Avatar>
                <Typography variant="h6" fontWeight="800" gutterBottom>{item.title}</Typography>
                <Typography variant="body2" sx={{ color: '#94A3B8', lineHeight: 1.6 }}>{item.desc}</Typography>
              </Paper>
            </Grid>
          ))}
        </Grid>
      </Container>

      {/* --- PRICING SECTION --- */}
      <Box sx={{ py: 20, bgcolor: '#0F172A' }}>
        <Container maxWidth="lg">
          <Box sx={{ textAlign: 'center', mb: 10 }}>
            <Typography variant="h3" fontWeight="900" gutterBottom>Une solution pour chaque équipe</Typography>
            <Typography variant="h6" sx={{ color: '#94A3B8' }}>Passez à la vitesse supérieure avec nos forfaits.</Typography>
          </Box>

          <Grid container spacing={4} alignItems="stretch">
            {/* Standard Plan Card Helper */}
            {[
              { name: "Gratuit", price: "0", feat: ["10 réunions / mois", "Transcription Standard", "Support par email"], cta: "Essayer gratuitement", active: false },
              { name: "Pro", price: "99", feat: ["Réunions illimitées", "IA Haute Précision", "Suggestions de tâches", "Custom Branding"], cta: "Démarrer maintenant", active: true },
              { name: "Entreprise", price: "499", feat: ["Sécurité ISO 27001", "Account Manager", "API personnalisée", "Rapports avancés"], cta: "Contacter Ventes", active: false }
            ].map((p, i) => (
              <Grid item xs={12} md={4} key={i}>
                <Paper sx={{ 
                  p: 6, height: '100%', borderRadius: 6, display: 'flex', flexDirection: 'column',
                  bgcolor: p.active ? 'rgba(255,255,255,0.05)' : 'transparent',
                  border: '1px solid', borderColor: p.active ? 'primary.main' : 'rgba(255,255,255,0.1)',
                  position: 'relative'
                }}>
                  {p.active && <Box sx={{ position: 'absolute', top: 25, right: 25, bgcolor: 'primary.main', color: 'white', px: 2, py: 0.5, borderRadius: 2, fontSize: '0.7rem', fontWeight: 900 }}>RECOMMANDÉ</Box>}
                  <Typography variant="h6" fontWeight="800" sx={{ mb: 1 }}>{p.name}</Typography>
                  <Box sx={{ display: 'flex', alignItems: 'baseline', mb: 4 }}>
                    <Typography variant="h2" fontWeight="900">${p.price}</Typography>
                    <Typography variant="subtitle1" sx={{ color: '#94A3B8', ml: 1 }}>/mois</Typography>
                  </Box>
                  <Stack spacing={2.5} sx={{ mb: 6, flexGrow: 1 }}>
                    {p.feat.map((f, j) => (
                      <Box key={j} sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <CheckIcon sx={{ color: 'primary.main', fontSize: 20 }} />
                        <Typography variant="body2" sx={{ opacity: 0.8 }}>{f}</Typography>
                      </Box>
                    ))}
                  </Stack>
                  <Button 
                    fullWidth 
                    variant={p.active ? "contained" : "outlined"} 
                    size="large"
                    sx={{ borderRadius: 3, py: 2, fontWeight: 800, textTransform: 'none' }}
                    onClick={() => handleStart(p.name.toUpperCase())}
                  >
                    {p.cta}
                  </Button>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* --- TRUST SECTION --- */}
      <Box sx={{ py: 10, textAlign: 'center', opacity: 0.5 }}>
        <Container maxWidth="lg">
          <Typography variant="overline" sx={{ letterSpacing: 4, fontWeight: 800 }}>DÉPLOYÉ DANS LES PLUS GRANDES ENTREPRISES</Typography>
          <Stack direction="row" spacing={8} justifyContent="center" sx={{ mt: 5, flexWrap: 'wrap', gap: 4 }}>
             {/* Mock Logo Icons */}
             <Stack direction="row" alignItems="center" spacing={1}><ShieldIcon /> <Typography variant="h6" fontWeight="900">BANK</Typography></Stack>
             <Stack direction="row" alignItems="center" spacing={1}><GrowthIcon /> <Typography variant="h6" fontWeight="900">TECH</Typography></Stack>
             <Stack direction="row" alignItems="center" spacing={1}><IAIcon /> <Typography variant="h6" fontWeight="900">AI-CORP</Typography></Stack>
             <Stack direction="row" alignItems="center" spacing={1}><LangIcon /> <Typography variant="h6" fontWeight="900">GLOBAL</Typography></Stack>
          </Stack>
        </Container>
      </Box>

      {/* --- FOOTER --- */}
      <Box sx={{ py: 10, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
        <Container maxWidth="lg">
          <Grid container spacing={8}>
            <Grid item xs={12} md={5}>
              <Typography variant="h6" fontWeight="900" sx={{ mb: 3 }}>Meeting Automation</Typography>
              <Typography variant="body2" sx={{ color: '#94A3B8', maxWidth: 300, lineHeight: 1.8 }}>
                Révolutionner la gestion des réunions grâce à l'IA souveraine optimisée pour le marché local.
              </Typography>
              <Stack direction="row" spacing={2} sx={{ mt: 4 }}>
                <Avatar sx={{ bgcolor: 'rgba(255,255,255,0.05)', cursor: 'pointer', '&:hover': { bgcolor: 'primary.main' } }}><ShieldIcon sx={{ fontSize: 20 }} /></Avatar>
                <Avatar sx={{ bgcolor: 'rgba(255,255,255,0.05)', cursor: 'pointer', '&:hover': { bgcolor: 'primary.main' } }}><LangIcon sx={{ fontSize: 20 }} /></Avatar>
              </Stack>
            </Grid>
            <Grid item xs={6} md={2}>
              <Typography variant="subtitle2" fontWeight="900" sx={{ mb: 3 }}>Produit</Typography>
              <Stack spacing={2}>
                <Typography variant="caption" sx={{ color: '#94A3B8', cursor: 'pointer', '&:hover': { color: 'white' } }}>Fonctionnalités</Typography>
                <Typography variant="caption" sx={{ color: '#94A3B8', cursor: 'pointer', '&:hover': { color: 'white' } }}>Tarifs</Typography>
                <Typography variant="caption" sx={{ color: '#94A3B8', cursor: 'pointer', '&:hover': { color: 'white' } }}>API</Typography>
              </Stack>
            </Grid>
            <Grid item xs={6} md={2}>
              <Typography variant="subtitle2" fontWeight="900" sx={{ mb: 3 }}>Société</Typography>
              <Stack spacing={2}>
                <Typography variant="caption" sx={{ color: '#94A3B8', cursor: 'pointer', '&:hover': { color: 'white' } }}>Support</Typography>
                <Typography variant="caption" sx={{ color: '#94A3B8', cursor: 'pointer', '&:hover': { color: 'white' } }}>Privacy</Typography>
                <Typography variant="caption" sx={{ color: '#94A3B8', cursor: 'pointer', '&:hover': { color: 'white' } }}>Contact</Typography>
              </Stack>
            </Grid>
            <Grid item xs={12} md={3}>
              <Typography variant="subtitle2" fontWeight="900" sx={{ mb: 3 }}>Sécurité</Typography>
              <Stack direction="row" spacing={2}>
                <Paper variant="outlined" sx={{ p: 2, bgcolor: 'transparent', borderColor: 'rgba(255,255,255,0.1)', color: 'white', flex: 1, textAlign: 'center' }}>
                  <ShieldIcon sx={{ mb: 1, color: 'primary.main' }} />
                  <Typography variant="caption" display="block">ISO 27001</Typography>
                </Paper>
                <Paper variant="outlined" sx={{ p: 2, bgcolor: 'transparent', borderColor: 'rgba(255,255,255,0.1)', color: 'white', flex: 1, textAlign: 'center' }}>
                  <CheckIcon sx={{ mb: 1, color: 'success.main' }} />
                  <Typography variant="caption" display="block">RGPD Compliant</Typography>
                </Paper>
              </Stack>
            </Grid>
          </Grid>
          <Box sx={{ mt: 10, pt: 4, borderTop: '1px solid rgba(255,255,255,0.05)', textAlign: 'center' }}>
            <Typography variant="caption" sx={{ color: '#475569' }}>
              © 2026 Meeting Automation. Conçu à Tunis. Propulsé par Mistral AI & Gladia.
            </Typography>
          </Box>
        </Container>
      </Box>
    </Box>
  );
};

export default LandingPage;