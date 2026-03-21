import React from 'react';
import { 
  Box, Container, Typography, Button, Grid, Stack, useTheme,
  AppBar, Toolbar, Paper, Accordion, AccordionSummary,
  AccordionDetails, Avatar, alpha, Link as MuiLink, Divider
} from '@mui/material';
import { 
  AutoFixHigh as IAIcon, AssignmentTurnedIn as ActionIcon, RecordVoiceOver as VoiceIcon,
  CheckCircle as CheckIcon, ExpandMore as ExpandMoreIcon, Language as LangIcon,
  PlayArrow as PlayIcon, Security as ShieldIcon, TrendingUp as GrowthIcon
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

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      // Offset accounts for the fixed header height (70px) plus some breathing room
      const offset = 100;
      const bodyRect = document.body.getBoundingClientRect().top;
      const elementRect = element.getBoundingClientRect().top;
      const elementPosition = elementRect - bodyRect;
      const offsetPosition = elementPosition - offset;
      
      window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
    }
  };

  return (
    <Box sx={{ 
      bgcolor: '#050B14', 
      minHeight: '100vh', 
      color: '#FFFFFF', 
      overflowX: 'hidden', 
      fontFamily: '"Inter", "Roboto", sans-serif',
      position: 'relative'
    }}>
      
      {/* Global CSS Animations */}
      <style>
        {`
          @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-15px); }
            100% { transform: translateY(0px); }
          }
          @keyframes gradient-x {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
          }
          @keyframes pulse-glow {
            0% { box-shadow: 0 0 0 0 rgba(0, 112, 243, 0.4); }
            70% { box-shadow: 0 0 0 15px rgba(0, 112, 243, 0); }
            100% { box-shadow: 0 0 0 0 rgba(0, 112, 243, 0); }
          }
          ::-webkit-scrollbar { width: 8px; }
          ::-webkit-scrollbar-track { background: #050B14; }
          ::-webkit-scrollbar-thumb { background: #1E293B; border-radius: 4px; }
          ::-webkit-scrollbar-thumb:hover { background: #334155; }
        `}
      </style>

      {/* Ambient Background Glows */}
      <Box sx={{ position: 'absolute', top: '-10%', left: '10%', width: '40vw', height: '40vw', background: `radial-gradient(circle, ${alpha('#0070F3', 0.15)} 0%, rgba(0,0,0,0) 70%)`, filter: 'blur(80px)', zIndex: 0, pointerEvents: 'none' }} />
      <Box sx={{ position: 'absolute', top: '30%', right: '-5%', width: '35vw', height: '35vw', background: `radial-gradient(circle, ${alpha('#7928CA', 0.1)} 0%, rgba(0,0,0,0) 70%)`, filter: 'blur(80px)', zIndex: 0, pointerEvents: 'none' }} />

      {/* --- NAVIGATION --- */}
      <AppBar position="fixed" elevation={0} sx={{ bgcolor: 'rgba(5, 11, 20, 0.75)', backdropFilter: 'blur(16px)', borderBottom: '1px solid rgba(255,255,255,0.05)', zIndex: 50 }}>
        <Container maxWidth="xl">
          <Toolbar disableGutters sx={{ justifyContent: 'space-between', height: 70 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }} onClick={() => window.scrollTo({top: 0, behavior: 'smooth'})}>
              <Box sx={{ width: 32, height: 32, bgcolor: '#0070F3', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', mr: 1.5, boxShadow: '0 4px 14px rgba(0,112,243,0.4)'}}>
                <IAIcon sx={{ color: 'white', fontSize: 18 }} />
              </Box>
              <Typography variant="h6" fontWeight="800" sx={{ letterSpacing: '-0.5px', color: 'white' }}>
                Meeting<Box component="span" sx={{ color: '#0070F3' }}>Automation</Box>
              </Typography>
            </Box>
            
            <Stack direction="row" spacing={4} alignItems="center">
              <Stack direction="row" spacing={3} sx={{ display: {xs: 'none', md: 'flex'} }}>
                <MuiLink component="button" onClick={() => scrollToSection('features')} variant="body2" sx={{ color: '#94A3B8', textDecoration: 'none', fontWeight: 600, transition: '0.2s', '&:hover': { color: 'white' } }}>Fonctionnalités</MuiLink>
                <MuiLink component="button" onClick={() => scrollToSection('pricing')} variant="body2" sx={{ color: '#94A3B8', textDecoration: 'none', fontWeight: 600, transition: '0.2s', '&:hover': { color: 'white' } }}>Tarifs</MuiLink>
                <MuiLink component="button" onClick={() => scrollToSection('faq')} variant="body2" sx={{ color: '#94A3B8', textDecoration: 'none', fontWeight: 600, transition: '0.2s', '&:hover': { color: 'white' } }}>FAQ</MuiLink>
              </Stack>
              
              <Box sx={{ display: {xs: 'none', sm: 'block'}, width: '1px', height: 20, bgcolor: 'rgba(255,255,255,0.1)' }} />

              <Button sx={{ color: 'white', fontWeight: 600, textTransform: 'none', fontSize: '0.9rem', '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' } }} onClick={() => navigate('/login')}>
                Connexion
              </Button>
              <Button 
                variant="contained" 
                sx={{ 
                  borderRadius: '8px', px: 2.5, py: 1, fontWeight: 700, textTransform: 'none', fontSize: '0.9rem',
                  background: 'linear-gradient(90deg, #0070F3 0%, #00A3FF 100%)',
                  boxShadow: '0 4px 14px rgba(0,112,243,0.4)',
                  animation: 'pulse-glow 2s infinite',
                  '&:hover': { background: 'linear-gradient(90deg, #00A3FF 0%, #0070F3 100%)' }
                }}
                onClick={() => handleStart()}
              >
                Démarrer
              </Button>
            </Stack>
          </Toolbar>
        </Container>
      </AppBar>

      {/* --- HERO SECTION --- */}
      <Box sx={{ pt: { xs: 15, md: 20 }, pb: { xs: 10, md: 15 }, position: 'relative', zIndex: 1 }}>
        <Container maxWidth="lg">
          <Grid container spacing={6} alignItems="center">
            
            {/* Text Content */}
            <Grid item xs={12} md={6}>
              <Box sx={{ textAlign: { xs: 'center', md: 'left' }, pr: { md: 4 } }}>
                <Typography 
                  variant="overline" 
                  sx={{ 
                    color: '#00A3FF', fontWeight: 800, letterSpacing: 1.5, fontSize: '0.7rem',
                    border: '1px solid rgba(0, 163, 255, 0.3)', px: 1.5, py: 0.5, borderRadius: 2, 
                    bgcolor: 'rgba(0, 163, 255, 0.05)', display: 'inline-block', mb: 3
                  }}
                >
                  🚀 LA NOUVELLE ÈRE DES RÉUNIONS
                </Typography>
                <Typography 
                  variant="h1" 
                  sx={{ 
                    fontSize: { xs: '2.5rem', sm: '3.5rem', md: '4.2rem' }, fontWeight: 900, mb: 3,
                    lineHeight: 1.1, letterSpacing: '-1.5px',
                    background: 'linear-gradient(to right, #FFFFFF 20%, #94A3B8 100%)',
                    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
                  }}
                >
                  Vos réunions, <br/>
                  <Box component="span" sx={{ 
                    background: 'linear-gradient(270deg, #00A3FF 0%, #0070F3 100%)', 
                    backgroundSize: '200% auto', animation: 'gradient-x 3s ease infinite',
                    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' 
                  }}>
                    résumées par l'IA.
                  </Box>
                </Typography>
                <Typography variant="body1" sx={{ color: '#94A3B8', mb: 5, fontSize: '1.1rem', lineHeight: 1.6, maxWidth: 500, mx: { xs: 'auto', md: 0 } }}>
                  Gagnez 5 heures par semaine. L'IA transcrit vos échanges, extrait les décisions et assigne les tâches automatiquement, avec une précision parfaite pour le marché Maghrébin.
                </Typography>
                
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} justifyContent={{ xs: 'center', md: 'flex-start' }}>
                  <Button 
                    variant="contained" 
                    size="large"
                    sx={{ borderRadius: '10px', px: 4, py: 1.5, fontWeight: 700, textTransform: 'none', fontSize: '1rem', background: '#FFFFFF', color: '#050B14', '&:hover': { background: '#E2E8F0' } }}
                    onClick={() => handleStart('PRO')}
                  >
                    Essayer gratuitement
                  </Button>
                  <Button 
                    variant="outlined" 
                    size="large"
                    startIcon={<PlayIcon />}
                    sx={{ borderRadius: '10px', px: 4, py: 1.5, fontWeight: 700, textTransform: 'none', color: '#FFFFFF', borderColor: 'rgba(255,255,255,0.2)', '&:hover': { borderColor: '#FFFFFF', bgcolor: 'rgba(255,255,255,0.05)' } }}
                  >
                    Voir la vidéo
                  </Button>
                </Stack>
              </Box>
            </Grid>

            {/* Floating Image Mockup */}
            <Grid item xs={12} md={6}>
              <Box sx={{ position: 'relative', width: '100%', animation: 'float 6s ease-in-out infinite' }}>
                {/* Decoration Glow behind image */}
                <Box sx={{ position: 'absolute', top: '10%', left: '10%', right: '10%', bottom: '10%', background: '#0070F3', filter: 'blur(60px)', opacity: 0.3, borderRadius: '50%' }}/>
                
                <Paper 
                  elevation={24}
                  sx={{ 
                    p: 0.5, borderRadius: '16px', bgcolor: 'rgba(255,255,255,0.02)', 
                    border: '1px solid rgba(255,255,255,0.1)', backdropFilter: 'blur(20px)',
                    boxShadow: '0 30px 60px rgba(0,0,0,0.6)', position: 'relative', zIndex: 2
                  }}
                >
                  <Box sx={{ borderRadius: '12px', overflow: 'hidden', bgcolor: '#0F172A' }}>
                    <Box sx={{ height: 24, bgcolor: 'rgba(255,255,255,0.02)', display: 'flex', alignItems: 'center', px: 1.5, gap: 0.8, borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: '#EF4444' }} />
                      <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: '#EAB308' }} />
                      <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: '#22C55E' }} />
                    </Box>
                    <Box component="img" 
                      src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1000&q=80"
                      sx={{ width: '100%', display: 'block', opacity: 0.85 }}
                      alt="Dashboard UI"
                    />
                    
                    {/* Floating Widget inside mockup */}
                    <Paper sx={{ 
                      position: 'absolute', bottom: '15%', left: '-5%', p: 1.5, borderRadius: 3, 
                      bgcolor: 'rgba(15, 23, 42, 0.85)', color: 'white', display: 'flex', alignItems: 'center', gap: 1.5,
                      border: '1px solid rgba(255,255,255,0.1)', backdropFilter: 'blur(12px)',
                      boxShadow: '0 15px 35px rgba(0,0,0,0.5)'
                    }}>
                      <Box sx={{ width: 36, height: 36, borderRadius: '50%', bgcolor: 'success.main', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <CheckIcon sx={{ color: 'white', fontSize: 20 }} />
                      </Box>
                      <Box>
                        <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 600, display: 'block' }}>RÉSUMÉ GÉNÉRÉ</Typography>
                        <Typography variant="body2" fontWeight="800">4 Tâches Extraites</Typography>
                      </Box>
                    </Paper>
                  </Box>
                </Paper>
              </Box>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* --- LOGO STRIP (SOCIAL PROOF) --- */}
      <Box sx={{ py: 4, borderTop: '1px solid rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.03)', bgcolor: 'rgba(255,255,255,0.01)' }}>
        <Container maxWidth="lg" sx={{ textAlign: 'center' }}>
          <Typography variant="caption" sx={{ color: '#64748B', fontWeight: 700, letterSpacing: 2, display: 'block', mb: 3 }}>ILS NOUS FONT CONFIANCE</Typography>
          <Stack direction="row" justifyContent="center" spacing={{ xs: 4, md: 8 }} flexWrap="wrap" sx={{ opacity: 0.4 }}>
             <Typography variant="h6" fontWeight="900" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><ShieldIcon /> FINCORP</Typography>
             <Typography variant="h6" fontWeight="900" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><GrowthIcon /> NEXUS</Typography>
             <Typography variant="h6" fontWeight="900" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><IAIcon /> AI-LAB</Typography>
             <Typography variant="h6" fontWeight="900" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><LangIcon /> GLOBAL</Typography>
          </Stack>
        </Container>
      </Box>

      {/* --- FEATURES BENTO BOX --- */}
      <Box id="features" sx={{ pt: 12, pb: 8 }}>
        <Container maxWidth="lg">
          <Box sx={{ textAlign: 'center', mb: 8 }}>
            <Typography variant="h3" fontWeight="800" gutterBottom>Une productivité redéfinie</Typography>
            <Typography variant="h6" sx={{ color: '#94A3B8', fontWeight: 400, maxWidth: 600, mx: 'auto' }}>
              Tout ce dont vous avez besoin pour gérer l'avant, le pendant et l'après-réunion, dans une interface unifiée.
            </Typography>
          </Box>
          
          <Grid container spacing={3}>
            {/* Feature 1 - Large */}
            <Grid item xs={12} md={8}>
              <Paper sx={{ p: 4, height: '100%', bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 4, position: 'relative', overflow: 'hidden', '&:hover': { bgcolor: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.1)' } }}>
                <Box sx={{ position: 'absolute', right: -20, top: -20, opacity: 0.1 }}><VoiceIcon sx={{ fontSize: 150, color: 'primary.main' }} /></Box>
                <Avatar sx={{ bgcolor: alpha('#0070F3', 0.15), color: '#00A3FF', mb: 2, width: 48, height: 48 }}><VoiceIcon /></Avatar>
                <Typography variant="h5" fontWeight="800" gutterBottom>Diarisation Hyper-Précise</Typography>
                <Typography variant="body1" sx={{ color: '#94A3B8', lineHeight: 1.6, maxWidth: '80%' }}>
                  Notre technologie Gladia V2 sépare automatiquement les voix des participants, attribue les paroles à la bonne personne et ignore les bruits de fond pour une transcription parfaite.
                </Typography>
              </Paper>
            </Grid>

            {/* Feature 2 - Small */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 4, height: '100%', bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 4, '&:hover': { bgcolor: 'rgba(255,255,255,0.03)' } }}>
                <Avatar sx={{ bgcolor: alpha('#22C55E', 0.15), color: '#22C55E', mb: 2, width: 48, height: 48 }}><ActionIcon /></Avatar>
                <Typography variant="h6" fontWeight="800" gutterBottom>To-Do List Auto</Typography>
                <Typography variant="body2" sx={{ color: '#94A3B8', lineHeight: 1.6 }}>
                  L'IA détecte les engagements pris et génère les tâches. Fini les oublis post-réunion.
                </Typography>
              </Paper>
            </Grid>

            {/* Feature 3 - Small */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 4, height: '100%', bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 4, '&:hover': { bgcolor: 'rgba(255,255,255,0.03)' } }}>
                <Avatar sx={{ bgcolor: alpha('#EAB308', 0.15), color: '#EAB308', mb: 2, width: 48, height: 48 }}><LangIcon /></Avatar>
                <Typography variant="h6" fontWeight="800" gutterBottom>Natif Maghreb</Typography>
                <Typography variant="body2" sx={{ color: '#94A3B8', lineHeight: 1.6 }}>
                  Le seul moteur comprenant le code-switching entre Français, Anglais et Darija (Arabe Tunisien).
                </Typography>
              </Paper>
            </Grid>

            {/* Feature 4 - Large */}
            <Grid item xs={12} md={8}>
              <Paper sx={{ p: 4, height: '100%', bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 4, position: 'relative', overflow: 'hidden', '&:hover': { bgcolor: 'rgba(255,255,255,0.03)' } }}>
                <Box sx={{ position: 'absolute', right: -20, top: -20, opacity: 0.1 }}><ShieldIcon sx={{ fontSize: 150, color: 'success.main' }} /></Box>
                <Avatar sx={{ bgcolor: alpha('#8B5CF6', 0.15), color: '#A78BFA', mb: 2, width: 48, height: 48 }}><ShieldIcon /></Avatar>
                <Typography variant="h5" fontWeight="800" gutterBottom>Sécurité ISO 27001 & RGPD</Typography>
                <Typography variant="body1" sx={{ color: '#94A3B8', lineHeight: 1.6, maxWidth: '80%' }}>
                  Vos données vous appartiennent. Architecture multi-tenant isolée, chiffrement AES-256 au repos et en transit, et hébergement souverain pour garantir la confidentialité absolue.
                </Typography>
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* --- PRICING SECTION --- */}
      <Box id="pricing" sx={{ py: 12, position: 'relative' }}>
        <Container maxWidth="lg">
          <Box sx={{ textAlign: 'center', mb: 8 }}>
            <Typography variant="h3" fontWeight="900" gutterBottom>Tarification transparente</Typography>
            <Typography variant="h6" sx={{ color: '#94A3B8', fontWeight: 400 }}>Un modèle simple qui évolue avec votre entreprise.</Typography>
          </Box>
          
          <Grid container spacing={3} justifyContent="center" alignItems="stretch">
            {[
              { name: "Gratuit", price: "0", desc: "Testez l'IA sur vos petites réunions.", feat: ["10 réunions / mois", "Transcription Standard", "Sans carte de crédit"], cta: "Créer un compte", highlight: false },
              { name: "Pro", price: "99", desc: "La puissance complète pour les managers.", feat: ["Réunions illimitées", "IA Mistral Haute Précision", "Extracteur de Tâches", "Exports PDF personnalisés"], cta: "Démarrer l'essai gratuit", highlight: true },
              { name: "Enterprise", price: "499", desc: "Sécurité et contrôle total.", feat: ["Hébergement dédié", "Conformité ISO 27001", "SLA 99.9% garanti", "Account Manager"], cta: "Contacter les ventes", highlight: false }
            ].map((p, i) => (
              <Grid item xs={12} md={4} key={i}>
                <Paper sx={{ 
                  p: 4, borderRadius: 4, display: 'flex', flexDirection: 'column', height: '100%',
                  bgcolor: p.highlight ? 'rgba(0,112,243,0.05)' : 'rgba(255,255,255,0.02)',
                  border: '1px solid', borderColor: p.highlight ? '#0070F3' : 'rgba(255,255,255,0.05)',
                  position: 'relative', transition: '0.3s', '&:hover': { transform: 'translateY(-5px)', borderColor: p.highlight ? '#00A3FF' : 'rgba(255,255,255,0.1)' }
                }}>
                  {p.highlight && (
                    <Box sx={{ position: 'absolute', top: -14, left: '50%', transform: 'translateX(-50%)', bgcolor: '#0070F3', color: 'white', px: 2, py: 0.5, borderRadius: 2, fontSize: '0.75rem', fontWeight: 800, letterSpacing: 1, boxShadow: '0 4px 10px rgba(0,112,243,0.4)' }}>
                      POPULAIRE
                    </Box>
                  )}
                  <Typography variant="h5" fontWeight="800" color={p.highlight ? 'primary.main' : 'inherit'}>{p.name}</Typography>
                  <Typography variant="body2" sx={{ color: '#94A3B8', mt: 1, mb: 3, minHeight: 40 }}>{p.desc}</Typography>
                  
                  <Box sx={{ display: 'flex', alignItems: 'flex-end', mb: 3 }}>
                    <Typography variant="h2" fontWeight="900" sx={{ lineHeight: 1 }}>${p.price}</Typography>
                    <Typography variant="body2" sx={{ color: '#94A3B8', ml: 1, mb: 0.5 }}>/mois</Typography>
                  </Box>
                  
                  <Divider sx={{ borderColor: 'rgba(255,255,255,0.05)', mb: 3 }} />
                  
                  <Stack spacing={2} sx={{ mb: 4, flexGrow: 1 }}>
                    {p.feat.map((f, j) => (
                      <Box key={j} sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <CheckIcon sx={{ color: p.highlight ? 'primary.main' : '#94A3B8', fontSize: 18 }} />
                        <Typography variant="body2" sx={{ color: '#E2E8F0', fontWeight: 500 }}>{f}</Typography>
                      </Box>
                    ))}
                  </Stack>
                  <Button 
                    fullWidth 
                    variant={p.highlight ? "contained" : "outlined"} 
                    size="large"
                    sx={{ 
                      borderRadius: '8px', fontWeight: 700, textTransform: 'none', py: 1.5,
                      ...(p.highlight && { background: 'linear-gradient(90deg, #0070F3 0%, #00A3FF 100%)', boxShadow: '0 4px 14px rgba(0,112,243,0.4)' }),
                      ...(!p.highlight && { borderColor: 'rgba(255,255,255,0.2)', color: 'white', '&:hover': { borderColor: 'white', bgcolor: 'rgba(255,255,255,0.05)' } })
                    }}
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

      {/* --- FAQ --- */}
      <Container id="faq" maxWidth="md" sx={{ py: 10 }}>
        <Typography variant="h4" textAlign="center" fontWeight="800" sx={{ mb: 6 }}>Questions fréquentes</Typography>
        {[
          { q: "Quelles langues sont supportées ?", a: "Le système gère nativement le Français, l'Anglais et l'Arabe Tunisien (Darija). La particularité de notre modèle est qu'il comprend parfaitement le 'code-switching' (le fait de changer de langue au milieu d'une phrase)." },
          { q: "Mes données sont-elles sécurisées et privées ?", a: "Absolument. Nous sommes conformes ISO 27001 et RGPD. Contrairement aux modèles publics, vos données ne sont jamais utilisées pour entraîner nos algorithmes. Chaque client dispose d'une base de données cloisonnée." },
          { q: "Puis-je annuler mon abonnement ?", a: "Oui, vous pouvez résilier ou modifier votre forfait à tout moment depuis votre tableau de bord administrateur, sans aucun frais caché." }
        ].map((faq, index) => (
          <Accordion key={index} elevation={0} disableGutters sx={{ bgcolor: 'transparent', color: 'white', borderBottom: '1px solid rgba(255,255,255,0.05)', '&:before': { display: 'none' }, mb: 1 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon sx={{ color: 'white' }} />} sx={{ px: 0, py: 1 }}>
              <Typography variant="h6" fontWeight="600" sx={{ fontSize: '1.1rem' }}>{faq.q}</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ px: 0, pb: 3 }}>
              <Typography variant="body1" sx={{ color: '#94A3B8', lineHeight: 1.6 }}>{faq.a}</Typography>
            </AccordionDetails>
          </Accordion>
        ))}
      </Container>

      {/* --- FOOTER --- */}
      <Box sx={{ pt: 8, pb: 4, borderTop: '1px solid rgba(255,255,255,0.05)', bgcolor: 'rgba(0,0,0,0.2)' }}>
        <Container maxWidth="lg">
          <Grid container spacing={4} sx={{ mb: 6 }}>
            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Box sx={{ width: 24, height: 24, bgcolor: '#0070F3', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', mr: 1}}>
                  <IAIcon sx={{ color: 'white', fontSize: 14 }} />
                </Box>
                <Typography variant="h6" fontWeight="900" sx={{ letterSpacing: '-0.5px' }}>MeetingAutomation</Typography>
              </Box>
              <Typography variant="body2" sx={{ color: '#64748B', maxWidth: 300, lineHeight: 1.6 }}>
                Plateforme SaaS souveraine pour automatiser la rédaction de vos Procès-Verbaux.
              </Typography>
            </Grid>
            <Grid item xs={6} md={3}>
              <Typography variant="subtitle2" fontWeight="800" sx={{ mb: 2, color: 'white' }}>Navigation</Typography>
              <Stack spacing={1.5}>
                <MuiLink component="button" onClick={() => scrollToSection('features')} variant="body2" sx={{ color: '#64748B', textDecoration: 'none', textAlign: 'left', '&:hover': { color: 'white' } }}>Fonctionnalités</MuiLink>
                <MuiLink component="button" onClick={() => scrollToSection('pricing')} variant="body2" sx={{ color: '#64748B', textDecoration: 'none', textAlign: 'left', '&:hover': { color: 'white' } }}>Tarifs</MuiLink>
                <MuiLink component="button" onClick={() => navigate('/login')} variant="body2" sx={{ color: '#64748B', textDecoration: 'none', textAlign: 'left', '&:hover': { color: 'white' } }}>Connexion</MuiLink>
              </Stack>
            </Grid>
            <Grid item xs={6} md={3}>
              <Typography variant="subtitle2" fontWeight="800" sx={{ mb: 2, color: 'white' }}>Légal</Typography>
              <Stack spacing={1.5}>
                <MuiLink href="#" variant="body2" sx={{ color: '#64748B', textDecoration: 'none', '&:hover': { color: 'white' } }}>Confidentialité</MuiLink>
                <MuiLink href="#" variant="body2" sx={{ color: '#64748B', textDecoration: 'none', '&:hover': { color: 'white' } }}>Mentions Légales</MuiLink>
                <MuiLink href="#" variant="body2" sx={{ color: '#64748B', textDecoration: 'none', '&:hover': { color: 'white' } }}>Certificat ISO 27001</MuiLink>
              </Stack>
            </Grid>
          </Grid>
          <Divider sx={{ borderColor: 'rgba(255,255,255,0.05)', mb: 3 }} />
          <Typography variant="caption" sx={{ color: '#475569', display: 'block', textAlign: 'center' }}>
            © 2026 Meeting Automation. Conçu pour le Maghreb. Powered by Mistral AI.
          </Typography>
        </Container>
      </Box>
    </Box>
  );
};

export default LandingPage;