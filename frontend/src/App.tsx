import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity,
  Bell,
  Moon,
  Sun,
  User,
  Settings,
  LogOut,
  Menu,
  X,
  Heart,
  ChevronDown,
} from 'lucide-react';
import {
  Button,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  Avatar,
  AvatarFallback,
  AvatarImage,
  Badge,
  Card,
} from '@/components/ui';
import {
  Dashboard,
  MedicationList,
  Chat,
  SymptomReport,
  ProfileModal,
  SettingsModal,
  LoginSignup,
} from '@/components';
import { usePatientStore } from '@/stores/patientStore';
import { cn } from '@/lib/utils';

type TabValue = 'dashboard' | 'medications' | 'agents' | 'chat' | 'symptoms';

type NotificationItem = {
  id: string;
  message: string;
  time: string;
  type?: string;
};

export default function App() {
  const {
    currentPatient,
    theme,
    setTheme,
    resetStore,
    setNotificationCount,
  } = usePatientStore();
  const [activeTab, setActiveTab] = useState<TabValue>('dashboard');
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);

  // Use per-patient storage so notifications are user-specific
  const notificationStorageKey = useMemo(() => {
    return currentPatient ? `patient-notifications-${currentPatient.id}` : null;
  }, [currentPatient]);

  // Toggle dark mode
  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
  };

  // Initialize theme
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';
      root.classList.remove('light', 'dark');
      root.classList.add(systemTheme);
    } else {
      root.classList.remove('light', 'dark');
      root.classList.add(theme);
    }
  }, [theme]);

  const isDark = theme === 'dark' || 
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setShowNotifications(false);
      setShowUserMenu(false);
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  // Load user-specific notifications
  useEffect(() => {
    if (!notificationStorageKey) {
      setNotifications([]);
      setNotificationCount(0);
      return;
    }

    const stored = localStorage.getItem(notificationStorageKey);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as NotificationItem[];
        setNotifications(parsed);
        setNotificationCount(parsed.length);
        return;
      } catch (error) {
        console.error('Failed to parse notifications', error);
      }
    }

    setNotifications([]);
    setNotificationCount(0);
  }, [notificationStorageKey, setNotificationCount]);

  // Persist notifications when they change
  useEffect(() => {
    if (!notificationStorageKey) return;
    localStorage.setItem(notificationStorageKey, JSON.stringify(notifications));
    setNotificationCount(notifications.length);
  }, [notifications, notificationStorageKey, setNotificationCount]);

  const handleClearNotifications = () => {
    if (!notificationStorageKey) return;
    localStorage.removeItem(notificationStorageKey);
    setNotifications([]);
    setNotificationCount(0);
    setShowNotifications(false);
  };

  // Show login/signup page if no patient is logged in
  if (!currentPatient) {
    return <LoginSignup />;
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex h-16 items-center justify-between px-6 w-full">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="p-2 bg-primary rounded-lg"
            >
              <Heart className="h-6 w-6 text-primary-foreground" />
            </motion.div>
            <div className="hidden sm:block">
              <h1 className="text-xl font-bold bg-gradient-to-r from-primary to-purple-600 bg-clip-text text-transparent">
                AdherenceGuardian
              </h1>
              <p className="text-xs text-muted-foreground">
                Your AI Health Companion
              </p>
            </div>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-2">
            {/* Theme Toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={(e) => {
                e.stopPropagation();
                toggleTheme();
              }}
              className="relative"
            >
              <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
              <span className="sr-only">Toggle theme</span>
            </Button>

            {/* Notifications */}
            <div className="relative">
              <Button
                variant="ghost"
                size="icon"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowNotifications(!showNotifications);
                  setShowUserMenu(false);
                }}
                className="relative"
              >
                <Bell className="h-5 w-5" />
                {notifications.length > 0 && (
                  <span className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-red-500 text-xs text-white flex items-center justify-center">
                    {notifications.length}
                  </span>
                )}
              </Button>

              <AnimatePresence>
                {showNotifications && (
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute right-0 mt-2 w-80 rounded-lg border bg-popover shadow-lg"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="p-3 border-b">
                      <h3 className="font-semibold">Notifications</h3>
                    </div>
                    <div className="max-h-80 overflow-auto">
                      {notifications.length === 0 ? (
                        <div className="p-3 text-sm text-muted-foreground">
                          You do not have any notifications yet.
                        </div>
                      ) : (
                        notifications.map((notif) => (
                          <div
                            key={notif.id}
                            className="p-3 border-b last:border-0 hover:bg-muted/50 cursor-pointer"
                          >
                            <p className="text-sm">{notif.message}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {notif.time}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="p-2 border-t flex gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full"
                        onClick={handleClearNotifications}
                        disabled={notifications.length === 0}
                      >
                        Clear notifications
                      </Button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* User Menu */}
            <div className="relative">
              <Button
                variant="ghost"
                className="flex items-center gap-2 px-2"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowUserMenu(!showUserMenu);
                  setShowNotifications(false);
                }}
              >
                <Avatar className="h-8 w-8">
                  <AvatarImage src={currentPatient?.avatar_url} />
                  <AvatarFallback className="bg-primary text-primary-foreground">
                    {currentPatient?.name?.charAt(0) || 'J'}
                  </AvatarFallback>
                </Avatar>
                <span className="hidden lg:inline-block font-medium">
                  {currentPatient?.name || 'John Doe'}
                </span>
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              </Button>

              <AnimatePresence>
                {showUserMenu && (
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute right-0 mt-2 w-56 rounded-lg border bg-popover shadow-lg"
                    onClick={(e) => e.stopPropagation()
                    }
                  >
                    <div className="p-3 border-b">
                      <p className="font-medium">{currentPatient?.name || 'John Doe'}</p>
                      <p className="text-sm text-muted-foreground">
                        {currentPatient?.email || 'john@example.com'}
                      </p>
                    </div>
                    <div className="p-2">
                      <Button
                        variant="ghost"
                        className="w-full justify-start"
                        size="sm"
                        onClick={() => {
                          setShowProfileModal(true);
                          setShowUserMenu(false);
                        }}
                      >
                        <User className="h-4 w-4 mr-2" />
                        Profile
                      </Button>
                      <Button
                        variant="ghost"
                        className="w-full justify-start"
                        size="sm"
                        onClick={() => {
                          setShowSettingsModal(true);
                          setShowUserMenu(false);
                        }}
                      >
                        <Settings className="h-4 w-4 mr-2" />
                        Settings
                      </Button>
                      <Button
                        variant="ghost"
                        className="w-full justify-start text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                        size="sm"
                        onClick={() => {
                          if (confirm('Are you sure you want to sign out?')) {
                            resetStore();
                            window.location.reload();
                          }
                        }}
                      >
                        <LogOut className="h-4 w-4 mr-2" />
                        Sign out
                      </Button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Mobile Menu Button */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            {isMobileMenuOpen ? (
              <X className="h-6 w-6" />
            ) : (
              <Menu className="h-6 w-6" />
            )}
          </Button>
        </div>

        {/* Mobile Menu */}
        <AnimatePresence>
          {isMobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden border-t"
            >
              <div className="container px-4 py-4 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Avatar className="h-10 w-10">
                      <AvatarFallback className="bg-primary text-primary-foreground">
                        {currentPatient?.name?.charAt(0) || 'J'}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="font-medium">{currentPatient?.name || 'John Doe'}</p>
                      <p className="text-sm text-muted-foreground">View profile</p>
                    </div>
                  </div>
                  <Button variant="ghost" size="icon" onClick={toggleTheme}>
                    {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                  </Button>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="flex-1">
                    <Settings className="h-4 w-4 mr-2" />
                    Settings
                  </Button>
                  <Button variant="outline" size="sm" className="flex-1">
                    <Bell className="h-4 w-4 mr-2" />
                    Notifications
                    {notifications.length > 0 && (
                      <Badge className="ml-2">{notifications.length}</Badge>
                    )}
                  </Button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* Main Content */}
      <main className="container px-4 py-6">
        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as TabValue)}
          className="space-y-6"
        >
          <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-grid">
            <TabsTrigger value="dashboard" className="gap-2">
              <Activity className="h-4 w-4 hidden sm:inline" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="medications" className="gap-2">
              <span className="hidden sm:inline">💊</span>
              Medications
            </TabsTrigger>
            <TabsTrigger value="chat" className="gap-2">
              <span className="hidden sm:inline">💬</span>
              AI Chat
            </TabsTrigger>
            <TabsTrigger value="symptoms" className="gap-2">
              <span className="hidden sm:inline">🩺</span>
              Symptoms
            </TabsTrigger>
          </TabsList>

          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.2 }}
            >
              <TabsContent value="dashboard" className="mt-0">
                <Dashboard />
              </TabsContent>

              <TabsContent value="medications" className="mt-0">
                <MedicationList />
              </TabsContent>

              <TabsContent value="chat" className="mt-0">
                <Chat />
              </TabsContent>

              <TabsContent value="symptoms" className="mt-0">
                <SymptomReport />
              </TabsContent>
            </motion.div>
          </AnimatePresence>
        </Tabs>
      </main>

      {/* Modals */}
      <ProfileModal
        isOpen={showProfileModal}
        onClose={() => setShowProfileModal(false)}
      />
      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
      />
    </div>
  );
}