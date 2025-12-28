import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Heart, Mail, Phone, Calendar, Loader2, LogIn, UserPlus } from 'lucide-react';
import {
  Button,
  Input,
  Card,
  CardContent,
  CardHeader,
} from '@/components/ui';
import { usePatientStore } from '@/stores/patientStore';
import { patientApi } from '@/services/api';

export default function LoginSignup() {
  const { setCurrentPatient, setDashboardStats, theme, setTheme } = usePatientStore();
  const [isLogin, setIsLogin] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const browserTimezone =
    (typeof Intl !== 'undefined' && Intl.DateTimeFormat().resolvedOptions().timeZone) ||
    'UTC';
    // Ensure theme applies on auth screen and default to dark
    useEffect(() => {
      const root = document.documentElement;
      root.classList.remove('light', 'dark');
      root.classList.add(theme === 'system'
        ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
        : theme);
    }, [theme]);

    const handleThemeToggle = () => {
      setTheme(theme === 'dark' ? 'light' : 'dark');
    };

    const loadDashboardStats = async (patientId: number) => {
      try {
        const stats = await patientApi.getDashboardStats(patientId);
        setDashboardStats(stats);
      } catch (err) {
        console.warn('Could not load dashboard stats for patient', patientId, err);
      }
    };
  
  const [loginData, setLoginData] = useState({
    email: '',
  });
  
  const [signupData, setSignupData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    dateOfBirth: '',
    conditions: '',
    allergies: '',
    timezone: browserTimezone,
  });

  const handleLoginChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLoginData({ ...loginData, [e.target.name]: e.target.value });
    setError(null);
  };

  const handleSignupChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSignupData({ ...signupData, [e.target.name]: e.target.value });
    setError(null);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginData.email) {
      setError('Please enter your email');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      // Try to find patient by email - fetch all and filter
      const patients = await patientApi.getAll();
      const patient = patients.find(p => p.email === loginData.email);
      
      if (patient) {
        // Fetch full patient details
        const fullPatient: any = await patientApi.getById(patient.id);
        const fullName = [fullPatient?.first_name, fullPatient?.last_name]
          .filter(Boolean)
          .join(' ')
          .trim() || fullPatient?.name || fullPatient?.email?.split('@')[0] || 'New User';
        setCurrentPatient({
          id: fullPatient.id,
          name: fullName,
          email: fullPatient.email,
          phone: fullPatient.phone,
          date_of_birth: fullPatient.date_of_birth,
          timezone: fullPatient.timezone || 'America/New_York',
          conditions: fullPatient.conditions || [],
          allergies: fullPatient.allergies || [],
          notification_preferences: fullPatient.notification_preferences || {},
          created_at: fullPatient.created_at,
          updated_at: fullPatient.updated_at,
          is_active: fullPatient.is_active,
        });
        loadDashboardStats(fullPatient.id);
      } else {
        setError('No account found with this email. Please sign up.');
      }
    } catch (err) {
      console.error('Login error:', err);
      setError('Failed to login. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!signupData.firstName || !signupData.lastName || !signupData.email) {
      setError('Please fill in all required fields');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const newPatient: any = await patientApi.create({
        first_name: signupData.firstName,
        last_name: signupData.lastName,
        email: signupData.email,
        phone: signupData.phone || undefined,
        date_of_birth: signupData.dateOfBirth || undefined,
        conditions: signupData.conditions ? signupData.conditions.split(',').map(c => c.trim()).filter(Boolean) : [],
        allergies: signupData.allergies ? signupData.allergies.split(',').map(a => a.trim()).filter(Boolean) : [],
        timezone: signupData.timezone || browserTimezone,
      } as any);
      
      const fullName = [newPatient?.first_name, newPatient?.last_name]
        .filter(Boolean)
        .join(' ')
        .trim() || newPatient.name || newPatient.email?.split('@')[0] || 'New User';
      setCurrentPatient({
        id: newPatient.id,
        name: fullName,
        email: newPatient.email,
        phone: newPatient.phone,
        date_of_birth: newPatient.date_of_birth,
        timezone: newPatient.timezone || 'America/New_York',
        conditions: newPatient.conditions || [],
        allergies: newPatient.allergies || [],
        notification_preferences: newPatient.notification_preferences || {},
        created_at: newPatient.created_at,
        updated_at: newPatient.updated_at,
        is_active: newPatient.is_active,
      });
      loadDashboardStats(newPatient.id);
    } catch (err: any) {
      console.error('Signup error:', err);
      if (err.response?.status === 400) {
        setError('An account with this email already exists. Please login.');
      } else {
        setError('Failed to create account. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setIsLoading(true);
    setError(null);
    setInfo('Loading demo account...');
    try {
      const patients = await patientApi.getAll();
      const demo = patients[0];
      if (!demo) {
        setError('No demo patients found. Please sign up.');
        return;
      }
      const fullPatient: any = await patientApi.getById(demo.id);
      const fullName = [fullPatient?.first_name, fullPatient?.last_name]
        .filter(Boolean)
        .join(' ')
        .trim() || fullPatient?.name || fullPatient?.email?.split('@')[0] || 'Demo User';
      setCurrentPatient({
        id: fullPatient.id,
        name: fullName,
        email: fullPatient.email,
        phone: fullPatient.phone,
        date_of_birth: fullPatient.date_of_birth,
        timezone: fullPatient.timezone || 'America/New_York',
        conditions: fullPatient.conditions || [],
        allergies: fullPatient.allergies || [],
        notification_preferences: fullPatient.notification_preferences || {},
        created_at: fullPatient.created_at,
        updated_at: fullPatient.updated_at,
        is_active: fullPatient.is_active,
      });
      loadDashboardStats(fullPatient.id);
      setInfo('');
    } catch (err) {
      console.error('Demo login error:', err);
      setError('Failed to load demo account. Please sign up.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="inline-flex p-4 bg-primary rounded-2xl mb-4"
          >
            <Heart className="h-10 w-10 text-primary-foreground" />
          </motion.div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-purple-600 bg-clip-text text-transparent">
            AdherenceGuardian
          </h1>
          <p className="text-muted-foreground mt-2">
            Your AI Health Companion
          </p>
        </div>

        <div className="flex justify-between items-center mb-2 text-sm text-muted-foreground">
          <span>Theme: {theme === 'dark' ? 'Dark' : theme === 'light' ? 'Light' : 'System'}</span>
          <Button variant="ghost" size="sm" onClick={handleThemeToggle}>
            Switch to {theme === 'dark' ? 'Light' : 'Dark'}
          </Button>
        </div>

        <Card className="border-2">
          <CardHeader className="pb-4">
            <div className="flex gap-2">
              <Button
                variant={isLogin ? 'default' : 'ghost'}
                className="flex-1"
                onClick={() => { setIsLogin(true); setError(null); }}
              >
                <LogIn className="h-4 w-4 mr-2" />
                Login
              </Button>
              <Button
                variant={!isLogin ? 'default' : 'ghost'}
                className="flex-1"
                onClick={() => { setIsLogin(false); setError(null); }}
              >
                <UserPlus className="h-4 w-4 mr-2" />
                Sign Up
              </Button>
            </div>
          </CardHeader>
          
          <CardContent className="space-y-3">
            {info && (
              <div className="p-3 rounded-md bg-blue-50 dark:bg-blue-900/30 text-sm text-blue-700 dark:text-blue-200">
                {info}
              </div>
            )}
            {isLogin ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <label className="text-sm font-medium mb-1.5 block flex items-center gap-2">
                    <Mail className="h-4 w-4" />
                    Email Address
                  </label>
                  <Input
                    name="email"
                    type="email"
                    placeholder="Enter your email"
                    value={loginData.email}
                    onChange={handleLoginChange}
                  />
                </div>
                
                {error && (
                  <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
                    <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
                  </div>
                )}
                
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Logging in...
                    </>
                  ) : (
                    <>
                      <LogIn className="h-4 w-4 mr-2" />
                      Login
                    </>
                  )}
                </Button>

                <Button
                  type="button"
                  variant="secondary"
                  className="w-full"
                  disabled={isLoading}
                  onClick={handleDemoLogin}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Loading demo...
                    </>
                  ) : (
                    <>
                      <Heart className="h-4 w-4 mr-2" />
                      Use Demo Account
                    </>
                  )}
                </Button>
              </form>
            ) : (
              <form onSubmit={handleSignup} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium mb-1.5 block">
                      First Name *
                    </label>
                    <Input
                      name="firstName"
                      placeholder="John"
                      value={signupData.firstName}
                      onChange={handleSignupChange}
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-1.5 block">
                      Last Name *
                    </label>
                    <Input
                      name="lastName"
                      placeholder="Doe"
                      value={signupData.lastName}
                      onChange={handleSignupChange}
                    />
                  </div>
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1.5 block flex items-center gap-2">
                    <Mail className="h-4 w-4" />
                    Email Address *
                  </label>
                  <Input
                    name="email"
                    type="email"
                    placeholder="john@example.com"
                    value={signupData.email}
                    onChange={handleSignupChange}
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1.5 block flex items-center gap-2">
                    <Phone className="h-4 w-4" />
                    Phone
                  </label>
                  <Input
                    name="phone"
                    placeholder="+1-555-0123"
                    value={signupData.phone}
                    onChange={handleSignupChange}
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1.5 block flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    Date of Birth
                  </label>
                  <Input
                    name="dateOfBirth"
                    type="date"
                    value={signupData.dateOfBirth}
                    onChange={handleSignupChange}
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    Medical Conditions
                  </label>
                  <Input
                    name="conditions"
                    placeholder="Type 2 Diabetes, Hypertension"
                    value={signupData.conditions}
                    onChange={handleSignupChange}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Separate with commas</p>
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    Allergies
                  </label>
                  <Input
                    name="allergies"
                    placeholder="Penicillin, Aspirin"
                    value={signupData.allergies}
                    onChange={handleSignupChange}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Separate with commas</p>
                </div>
                
                {error && (
                  <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
                    <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
                  </div>
                )}
                
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Creating Account...
                    </>
                  ) : (
                    <>
                      <UserPlus className="h-4 w-4 mr-2" />
                      Create Account
                    </>
                  )}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
