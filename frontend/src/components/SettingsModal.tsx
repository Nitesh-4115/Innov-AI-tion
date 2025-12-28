import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Settings, Bell, Moon, Sun, Clock, Volume2, Shield, Database, Loader2 } from 'lucide-react';
import {
  Button,
  Input,
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui';
import { usePatientStore } from '@/stores/patientStore';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { theme, setTheme } = usePatientStore();
  const [isSaving, setIsSaving] = useState(false);
  
  const [settings, setSettings] = useState({
    notifications: {
      email: true,
      push: true,
      sms: false,
      reminderMinutesBefore: 15,
    },
    display: {
      theme: theme,
      compactMode: false,
    },
    privacy: {
      shareDataWithProvider: true,
      anonymousAnalytics: true,
    },
    schedule: {
      wakeTime: '08:00',
      sleepTime: '22:00',
      breakfastTime: '08:00',
      lunchTime: '12:00',
      dinnerTime: '19:00',
    },
  });

  const handleNotificationChange = (key: string, value: boolean | number) => {
    setSettings(prev => ({
      ...prev,
      notifications: { ...prev.notifications, [key]: value },
    }));
  };

  const handleScheduleChange = (key: string, value: string) => {
    setSettings(prev => ({
      ...prev,
      schedule: { ...prev.schedule, [key]: value },
    }));
  };

  const handleThemeChange = (newTheme: 'light' | 'dark' | 'system') => {
    setSettings(prev => ({
      ...prev,
      display: { ...prev.display, theme: newTheme },
    }));
    setTheme(newTheme);
  };

  const handleSave = async () => {
    setIsSaving(true);
    await new Promise(resolve => setTimeout(resolve, 1000));
    setIsSaving(false);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="w-full max-w-2xl mx-4 max-h-[90vh] overflow-auto"
          onClick={(e) => e.stopPropagation()}
        >
          <Card className="border-2">
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <Settings className="h-5 w-5 text-primary" />
                </div>
                <CardTitle>Settings</CardTitle>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose}>
                <X className="h-5 w-5" />
              </Button>
            </CardHeader>
            
            <CardContent className="space-y-6">
              {/* Notifications */}
              <div className="space-y-4">
                <h3 className="font-semibold flex items-center gap-2">
                  <Bell className="h-4 w-4" />
                  Notifications
                </h3>
                <div className="space-y-3 pl-6">
                  <label className="flex items-center justify-between">
                    <span className="text-sm">Email Notifications</span>
                    <input
                      type="checkbox"
                      checked={settings.notifications.email}
                      onChange={(e) => handleNotificationChange('email', e.target.checked)}
                      className="h-4 w-4 rounded border-input bg-transparent"
                    />
                  </label>
                  <label className="flex items-center justify-between">
                    <span className="text-sm">Push Notifications</span>
                    <input
                      type="checkbox"
                      checked={settings.notifications.push}
                      onChange={(e) => handleNotificationChange('push', e.target.checked)}
                      className="h-4 w-4 rounded border-input bg-transparent"
                    />
                  </label>
                  <label className="flex items-center justify-between">
                    <span className="text-sm">SMS Reminders</span>
                    <input
                      type="checkbox"
                      checked={settings.notifications.sms}
                      onChange={(e) => handleNotificationChange('sms', e.target.checked)}
                      className="h-4 w-4 rounded border-input bg-transparent"
                    />
                  </label>
                  <label className="flex items-center justify-between">
                    <span className="text-sm">Remind me before dose (minutes)</span>
                    <select
                      value={settings.notifications.reminderMinutesBefore}
                      onChange={(e) => handleNotificationChange('reminderMinutesBefore', parseInt(e.target.value))}
                      className="w-24 h-8 px-2 rounded border bg-transparent text-sm"
                    >
                      <option value={5}>5 min</option>
                      <option value={10}>10 min</option>
                      <option value={15}>15 min</option>
                      <option value={30}>30 min</option>
                      <option value={60}>1 hour</option>
                    </select>
                  </label>
                </div>
              </div>
              
              {/* Display */}
              <div className="space-y-4 pt-4 border-t">
                <h3 className="font-semibold flex items-center gap-2">
                  <Sun className="h-4 w-4" />
                  Display
                </h3>
                <div className="space-y-3 pl-6">
                  <div>
                    <span className="text-sm block mb-2">Theme</span>
                    <div className="flex gap-2">
                      <Button
                        variant={settings.display.theme === 'light' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => handleThemeChange('light')}
                      >
                        <Sun className="h-4 w-4 mr-1" />
                        Light
                      </Button>
                      <Button
                        variant={settings.display.theme === 'dark' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => handleThemeChange('dark')}
                      >
                        <Moon className="h-4 w-4 mr-1" />
                        Dark
                      </Button>
                      <Button
                        variant={settings.display.theme === 'system' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => handleThemeChange('system')}
                      >
                        System
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Schedule Preferences */}
              <div className="space-y-4 pt-4 border-t">
                <h3 className="font-semibold flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Schedule Preferences
                </h3>
                <div className="grid grid-cols-2 gap-4 pl-6">
                  <div>
                    <label className="text-sm block mb-1">Wake Time</label>
                    <Input
                      type="time"
                      value={settings.schedule.wakeTime}
                      onChange={(e) => handleScheduleChange('wakeTime', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-sm block mb-1">Sleep Time</label>
                    <Input
                      type="time"
                      value={settings.schedule.sleepTime}
                      onChange={(e) => handleScheduleChange('sleepTime', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-sm block mb-1">Breakfast Time</label>
                    <Input
                      type="time"
                      value={settings.schedule.breakfastTime}
                      onChange={(e) => handleScheduleChange('breakfastTime', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-sm block mb-1">Lunch Time</label>
                    <Input
                      type="time"
                      value={settings.schedule.lunchTime}
                      onChange={(e) => handleScheduleChange('lunchTime', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-sm block mb-1">Dinner Time</label>
                    <Input
                      type="time"
                      value={settings.schedule.dinnerTime}
                      onChange={(e) => handleScheduleChange('dinnerTime', e.target.value)}
                    />
                  </div>
                </div>
              </div>
              
              {/* Privacy */}
              <div className="space-y-4 pt-4 border-t">
                <h3 className="font-semibold flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  Privacy
                </h3>
                <div className="space-y-3 pl-6">
                  <label className="flex items-center justify-between">
                    <div>
                      <span className="text-sm block">Share data with healthcare provider</span>
                      <span className="text-xs text-muted-foreground">Allow your provider to view adherence reports</span>
                    </div>
                    <input
                      type="checkbox"
                      checked={settings.privacy.shareDataWithProvider}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        privacy: { ...prev.privacy, shareDataWithProvider: e.target.checked }
                      }))}
                      className="h-4 w-4 rounded border-input bg-transparent"
                    />
                  </label>
                  <label className="flex items-center justify-between">
                    <div>
                      <span className="text-sm block">Anonymous analytics</span>
                      <span className="text-xs text-muted-foreground">Help improve the app with anonymous usage data</span>
                    </div>
                    <input
                      type="checkbox"
                      checked={settings.privacy.anonymousAnalytics}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        privacy: { ...prev.privacy, anonymousAnalytics: e.target.checked }
                      }))}
                      className="h-4 w-4 rounded border-input bg-transparent"
                    />
                  </label>
                </div>
              </div>
              
              {/* Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t">
                <Button variant="outline" onClick={onClose}>
                  Cancel
                </Button>
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save Settings'
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
