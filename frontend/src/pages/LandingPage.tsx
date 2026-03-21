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
  Avatar
} from '@mui/material';
import { 
  AutoFixHigh as IAIcon, 
  AssignmentTurnedIn as ActionIcon, 
  RecordVoiceOver as VoiceIcon,
  CheckCircle as CheckIcon,
  ExpandMore as ExpandMoreIcon,
  Language as LangIcon,
  Security as ShieldIcon,
  TrendingUp as GrowthIcon
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();

  const handleStart = (plan?: string) => {
    if (plan) {
      navigate(`/register?plan=${plan}`);
    } else {
      navigate('/login');
    }
  };

  return (
    <Box sx={{ bgcolor: '#FFFFFF', minHeight: '100vh', color: '#1A2027' }}>
      
      {/* --- NAVIGATION --- */}
      <AppBar 
        position="sticky" 
        elevation={0} 
        sx={{ 
          bgcolor: 'rgba(255, 255, 255, 0.8)', 
          backdropFilter: 'blur(20px)',
          color: '#1A2027', 
          borderBottom: '1px solid #E5EAF2' 
        }}
      >
        <Container maxWidth="lg">
          <Toolbar disableGutters sx={{ justifyContent: 'space-between', height: 70 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }} onClick={() => window.scrollTo(0,0)}>
              <Avatar sx={{ bgcolor: theme.palette.primary.main, mr: 1, width: 32, height: 32 }}>
                <IAIcon sx={{ fontSize: 20 }} />
              </Avatar>
              <Typography variant="h6" fontWeight="800" sx={{ letterSpacing: '-0.5px' }}>
                Meeting<Box component="span" sx={{ color: theme.palette.primary.main }}>Automation</Box>
              </Typography>
            </Box>
            
            <Stack direction="row" spacing={1} alignItems="center">
              <Button color="inherit" sx={{ fontWeight: 600, display: {xs: 'none', sm: 'block'} }} onClick={() => navigate('/login')}>
                Connexion
              </Button>
              <Button 
                variant="contained" 
                sx={{ 
                  borderRadius: '10px', 
                  px: 3, 
                  fontWeight: 700,
                  textTransform: 'none',
                  boxShadow: '0 4px 14px 0 rgba(0,118,255,0.39)'
                }}
                onClick={() => handleStart()}
              >
                Essayer gratuitement
              </Button>
            </Stack>
          </Toolbar>
        </Container>
      </AppBar>

      {/* --- HERO SECTION --- */}
      <Box sx={{ 
        pt: { xs: 10, md: 15 }, 
        pb: { xs: 8, md: 12 },
        background: 'radial-gradient(circle at 50% -20%, #E3F2FD 0%, #FFFFFF 80%)'
      }}>
        <Container maxWidth="lg">
          <Grid container spacing={4} alignItems="center">
            <Grid item xs={12} md={7}>
              <Box sx={{ textAlign: { xs: 'center', md: 'left' } }}>
                <Typography 
                  variant="overline" 
                  sx={{ 
                    color: 'primary.main', 
                    fontWeight: 800, 
                    letterSpacing: 2,
                    bgcolor: 'primary.light',
                    px: 2, py: 0.5, borderRadius: 2,
                    opacity: 0.8
                  }}
                >
                  L'INTELLIGENCE ARTIFICIELLE AU SERVICE DE VOS RÉUNIONS
                </Typography>
                <Typography 
                  variant="h1" 
                  sx={{ 
                    fontSize: { xs: '2.5rem', md: '4rem' }, 
                    fontWeight: 900, 
                    lineHeight: 1.1, 
                    mt: 3, mb: 3,
                    letterSpacing: '-1px'
                  }}
                >
                  Générez vos PV de réunion <Box component="span" sx={{ color: 'primary.main' }}>en un clic</Box>
                </Typography>
                <Typography variant="h5" color="text.secondary" sx={{ mb: 5, lineHeight: 1.6, maxWidth: 600 }}>
                  Transformez instantanément vos discussions en comptes-rendus structurés, identifiez les actions et optimisez le suivi de vos projets.
                </Typography>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} justifyContent={{ xs: 'center', md: 'flex-start' }}>
                  <Button 
                    variant="contained" 
                    size="large" 
                    sx={{ borderRadius: '12px', px: 5, py: 2, fontSize: '1.1rem', fontWeight: 700, textTransform: 'none' }}
                    onClick={() => handleStart('PRO')}
                  >
                    Démarrer maintenant
                  </Button>
                  <Button 
                    variant="outlined" 
                    size="large" 
                    sx={{ borderRadius: '12px', px: 5, py: 2, fontSize: '1.1rem', fontWeight: 700, textTransform: 'none', borderWidth: 2 }}
                  >
                    Voir la démo
                  </Button>
                </Stack>
              </Box>
            </Grid>
            <Grid item xs={12} md={5}>
              <Paper 
                elevation={24} 
                sx={{ 
                  p: 1, 
                  borderRadius: 4, 
                  overflow: 'hidden', 
                  transform: { md: 'rotate(2deg)' },
                  boxShadow: '0 20px 50px rgba(0,0,0,0.1)'
                }}
              >
                <Box 
                  component="img" 
                  src="https://images.unsplash.com/photo-1531403009284-440f080d1e12?auto=format&fit=crop&w=800&q=80" 
                  sx={{ width: '100%', borderRadius: 3, display: 'block' }}
                  alt="Application Dashboard Preview"
                />
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* --- HOW IT WORKS --- */}
      <Container maxWidth="lg" sx={{ py: 12 }}>
        <Typography variant="h3" textAlign="center" fontWeight="800" gutterBottom>Comment ça marche ?</Typography>
        <Typography variant="h6" textAlign="center" color="text.secondary" sx={{ mb: 10 }}>Trois étapes simples pour révolutionner votre productivité.</Typography>
        
        <Grid container spacing={6}>
          <Grid item xs={12} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Avatar sx={{ width: 80, height: 80, bgcolor: 'primary.light', color: 'primary.main', mx: 'auto', mb: 3 }}>
                <VoiceIcon sx={{ fontSize: 40 }} />
              </Avatar>
              <Typography variant="h5" fontWeight="700" gutterBottom>1. Enregistrez</Typography>
              <Typography color="text.secondary">Lancez l'enregistrement directement depuis votre navigateur ou téléchargez votre fichier audio.</Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Avatar sx={{ width: 80, height: 80, bgcolor: 'secondary.light', color: 'secondary.main', mx: 'auto', mb: 3 }}>
                <IAIcon sx={{ fontSize: 40 }} />
              </Avatar>
              <Typography variant="h5" fontWeight="700" gutterBottom>2. Analyse IA</Typography>
              <Typography color="text.secondary">Notre IA transcrit, identifie les interlocuteurs et extrait les points clés en quelques secondes.</Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Avatar sx={{ width: 80, height: 80, bgcolor: 'success.light', color: 'success.main', mx: 'auto', mb: 3 }}>
                <ActionIcon sx={{ fontSize: 40 }} />
              </Avatar>
              <Typography variant="h5" fontWeight="700" gutterBottom>3. Validez & Suivez</Typography>
              <Typography color="text.secondary">Générez votre PV PDF/Word et suivez l'exécution des actions assignées dans votre dashboard.</Typography>
            </Box>
          </Grid>
        </Grid>
      </Container>

      {/* --- PRICING SECTION --- */}
      <Box sx={{ py: 15, bgcolor: '#F8FAFC' }}>
        <Container maxWidth="lg">
          <Typography variant="h3" textAlign="center" fontWeight="800" gutterBottom>Une offre adaptée à chaque besoin</Typography>
          <Typography variant="h6" textAlign="center" color="text.secondary" sx={{ mb: 10 }}>Passez à la vitesse supérieure avec nos forfaits Premium.</Typography>

          <Grid container spacing={4} alignItems="stretch">
            {/* Free */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 5, height: '100%', borderRadius: 4, display: 'flex', flexDirection: 'column', transition: '0.3s', '&:hover': { transform: 'translateY(-10px)' } }}>
                <Typography variant="h6" fontWeight="700">Gratuit</Typography>
                <Typography variant="h3" fontWeight="800" sx={{ mt: 2, mb: 1 }}>0$</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>Pour tester la puissance de l'IA</Typography>
                <Divider sx={{ mb: 4 }} />
                <Stack spacing={2} sx={{ flexGrow: 1, mb: 5 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">10 réunions / mois</Typography></Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">Transcription Standard</Typography></Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">Génération PV Automatique</Typography></Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">Gestion des actions</Typography></Box>
                </Stack>
                <Button fullWidth variant="outlined" size="large" sx={{ borderRadius: 3, py: 1.5, fontWeight: 700 }} onClick={() => handleStart('GRATUIT')}>S'inscrire</Button>
              </Paper>
            </Grid>

            {/* Pro */}
            <Grid item xs={12} md={4}>
              <Paper 
                elevation={10}
                sx={{ 
                  p: 5, height: '100%', borderRadius: 4, display: 'flex', flexDirection: 'column', 
                  border: '2px solid', borderColor: 'primary.main', position: 'relative',
                  transition: '0.3s', '&:hover': { transform: 'translateY(-10px)' }
                }}
              >
                <Box sx={{ position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%) translateY(-50%)', bgcolor: 'primary.main', color: 'white', px: 3, py: 0.5, borderRadius: 10, fontSize: '0.75rem', fontWeight: 800 }}>POPULAIRE</Box>
                <Typography variant="h6" fontWeight="700" color="primary.main">Pro</Typography>
                <Typography variant="h3" fontWeight="800" sx={{ mt: 2, mb: 1 }}>99$</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>Pour les équipes dynamiques</Typography>
                <Divider sx={{ mb: 4 }} />
                <Stack spacing={2} sx={{ flexGrow: 1, mb: 5 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2" fontWeight="600">Réunions illimitées</Typography></Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">Transcription Haute Précision</Typography></Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">Suggestions IA Intelligentes</Typography></Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">Export PDF / Word illimité</Typography></Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">Support Prioritaire</Typography></Box>
                </Stack>
                <Button fullWidth variant="contained" size="large" sx={{ borderRadius: 3, py: 2, fontWeight: 800, boxShadow: '0 4px 14px 0 rgba(0,118,255,0.39)' }} onClick={() => handleStart('PRO')}>Commencer</Button>
              </Paper>
            </Grid>

            {/* Enterprise */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 5, height: '100%', borderRadius: 4, display: 'flex', flexDirection: 'column', transition: '0.3s', '&:hover': { transform: 'translateY(-10px)' } }}>
                <Typography variant="h6" fontWeight="700">Entreprise</Typography>
                <Typography variant="h3" fontWeight="800" sx={{ mt: 2, mb: 1 }}>499$</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>Pour les grandes organisations</Typography>
                <Divider sx={{ mb: 4 }} />
                <Stack spacing={2} sx={{ flexGrow: 1, mb: 5 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">Tout le plan Pro</Typography></Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">Account Manager Dédié</Typography></Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">API & Webhooks Personnalisés</Typography></Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">SSO & Sécurité Avancée</Typography></Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="success" sx={{ mr: 1.5, fontSize: 20 }} /><Typography variant="body2">Rapports d'Utilisation</Typography></Box>
                </Stack>
                <Button fullWidth variant="outlined" size="large" sx={{ borderRadius: 3, py: 1.5, fontWeight: 700 }} onClick={() => handleStart('ENTREPRISE')}>Contacter Ventes</Button>
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* --- FEATURES GRID --- */}
      <Container maxWidth="lg" sx={{ py: 15 }}>
        <Grid container spacing={10}>
          <Grid item xs={12} md={6}>
            <Avatar sx={{ bgcolor: 'primary.light', mb: 3 }}><ShieldIcon color="primary" /></Avatar>
            <Typography variant="h4" fontWeight="800" gutterBottom>Sécurité & Conformité ISO 27001</Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 4, lineHeight: 1.8 }}>
              Vos données sont sacrées. Nous appliquons les standards les plus stricts en matière de protection des données, avec un chiffrement de bout en bout et des pistes d'audit complètes.
            </Typography>
            <Stack spacing={2}>
              <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="primary" sx={{ mr: 1 }} /><Typography variant="body2">Hébergement Sécurisé (Cloud Souverain)</Typography></Box>
              <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="primary" sx={{ mr: 1 }} /><Typography variant="body2">Authentification Multi-Facteurs (MFA)</Typography></Box>
              <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="primary" sx={{ mr: 1 }} /><Typography variant="body2">Isolation Totale des Données Clients</Typography></Box>
            </Stack>
          </Grid>
          <Grid item xs={12} md={6}>
            <Avatar sx={{ bgcolor: 'secondary.light', mb: 3 }}><LangIcon color="secondary" /></Avatar>
            <Typography variant="h4" fontWeight="800" gutterBottom>Optimisé pour le Maghreb</Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 4, lineHeight: 1.8 }}>
              Unique sur le marché, notre moteur gère parfaitement le français, l'anglais et les dialectes locaux (Arabe Tunisien, Darija). Plus besoin de nettoyer vos transcriptions manuellement.
            </Typography>
            <Stack spacing={2}>
              <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="secondary" sx={{ mr: 1 }} /><Typography variant="body2">Multi-langues Natif (AR, FR, EN)</Typography></Box>
              <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="secondary" sx={{ mr: 1 }} /><Typography variant="body2">Calendrier Culturel & Jours Fériés</Typography></Box>
              <Box sx={{ display: 'flex', alignItems: 'center' }}><CheckIcon color="secondary" sx={{ mr: 1 }} /><Typography variant="body2">Exportations Format Procès-Verbal Local</Typography></Box>
            </Stack>
          </Grid>
        </Grid>
      </Container>

      {/* --- FAQ SECTION --- */}
      <Box sx={{ py: 12, bgcolor: '#FFFFFF' }}>
        <Container maxWidth="md">
          <Typography variant="h4" textAlign="center" fontWeight="800" sx={{ mb: 8 }}>Questions fréquentes</Typography>
          
          <Accordion elevation={0} sx={{ borderBottom: '1px solid #E5EAF2' }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography fontWeight="700">Comment l'IA identifie-t-elle les différents intervenants ?</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body2" color="text.secondary">
                Nous utilisons une technologie de "Diarisation" avancée qui analyse les empreintes vocales uniques de chaque participant pour les distinguer avec précision, même en cas de chevauchement.
              </Typography>
            </AccordionDetails>
          </Accordion>

          <Accordion elevation={0} sx={{ borderBottom: '1px solid #E5EAF2' }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography fontWeight="700">Mes enregistrements audio sont-ils conservés ?</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body2" color="text.secondary">
                Vos fichiers sont stockés de manière chiffrée sur nos serveurs. Vous pouvez choisir de les supprimer automatiquement après la génération du PV selon vos politiques internes de rétention.
              </Typography>
            </AccordionDetails>
          </Accordion>

          <Accordion elevation={0} sx={{ borderBottom: '1px solid #E5EAF2' }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography fontWeight="700">Puis-je personnaliser le format des PV exportés ?</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body2" color="text.secondary">
                Absolument ! Le plan Pro et Entreprise permettent d'ajouter votre logo, vos en-têtes personnalisés und d'utiliser vos propres templates de documents.
              </Typography>
            </AccordionDetails>
          </Accordion>
        </Container>
      </Box>

      {/* --- FINAL CTA --- */}
      <Box sx={{ py: 15, textAlign: 'center', background: theme.palette.primary.main, color: 'white' }}>
        <Container maxWidth="sm">
          <Typography variant="h3" fontWeight="800" gutterBottom>Prêt à transformer vos réunions ?</Typography>
          <Typography variant="h6" sx={{ mb: 6, opacity: 0.9 }}>Rejoignez les entreprises qui gagnent déjà 5h par semaine grâce à l'IA.</Typography>
          <Button 
            variant="contained" 
            size="large" 
            sx={{ bgcolor: 'white', color: 'primary.main', borderRadius: 4, px: 8, py: 2, fontSize: '1.2rem', fontWeight: 800, '&:hover': { bgcolor: '#F1F5F9' } }}
            onClick={() => handleStart('PRO')}
          >
            Démarrer l'essai gratuit
          </Button>
        </Container>
      </Box>

      {/* --- FOOTER --- */}
      <Box sx={{ py: 8, bgcolor: '#0F172A', color: '#94A3B8' }}>
        <Container maxWidth="lg">
          <Grid container spacing={8}>
            <Grid item xs={12} md={4}>
              <Typography variant="h6" color="white" fontWeight="800" sx={{ mb: 3 }}>Meeting Automation</Typography>
              <Typography variant="body2" sx={{ lineHeight: 1.8 }}>
                La première plateforme de gestion de réunions optimisée pour le marché maghrébin par l'intelligence artificielle.
              </Typography>
            </Grid>
            <Grid item xs={6} md={2}>
              <Typography variant="subtitle2" color="white" fontWeight="700" sx={{ mb: 2 }}>Produit</Typography>
              <Stack spacing={1}>
                <Typography variant="caption" sx={{ cursor: 'pointer', '&:hover': { color: 'white' } }}>Fonctionnalités</Typography>
                <Typography variant="caption" sx={{ cursor: 'pointer', '&:hover': { color: 'white' } }}>Tarifs</Typography>
                <Typography variant="caption" sx={{ cursor: 'pointer', '&:hover': { color: 'white' } }}>Démo</Typography>
              </Stack>
            </Grid>
            <Grid item xs={6} md={2}>
              <Typography variant="subtitle2" color="white" fontWeight="700" sx={{ mb: 2 }}>Société</Typography>
              <Stack spacing={1}>
                <Typography variant="caption" sx={{ cursor: 'pointer', '&:hover': { color: 'white' } }}>Support</Typography>
                <Typography variant="caption" sx={{ cursor: 'pointer', '&:hover': { color: 'white' } }}>Confidentialité</Typography>
                <Typography variant="caption" sx={{ cursor: 'pointer', '&:hover': { color: 'white' } }}>Contact</Typography>
              </Stack>
            </Grid>
            <Grid item xs={12} md={4}>
              <Typography variant="subtitle2" color="white" fontWeight="700" sx={{ mb: 2 }}>Certifications</Typography>
              <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
                <Paper variant="outlined" sx={{ p: 1, bgcolor: 'transparent', borderColor: '#334155', color: 'white', textAlign: 'center' }}>
                  <ShieldIcon sx={{ fontSize: 30 }} />
                  <Typography variant="caption" display="block">ISO 27001</Typography>
                </Paper>
                <Paper variant="outlined" sx={{ p: 1, bgcolor: 'transparent', borderColor: '#334155', color: 'white', textAlign: 'center' }}>
                  <ShieldIcon sx={{ fontSize: 30 }} />
                  <Typography variant="caption" display="block">RGPD</Typography>
                </Paper>
              </Stack>
            </Grid>
          </Grid>
          <Divider sx={{ my: 6, borderColor: '#1E293B' }} />
          <Typography variant="caption" textAlign="center" display="block">
            © 2026 Meeting Automation. Tous droits réservés. Propulsé par Mistral & Whisper.
          </Typography>
        </Container>
      </Box>
    </Box>
  );
};

export default LandingPage;