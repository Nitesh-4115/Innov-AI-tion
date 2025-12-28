import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, User, Mail, Phone, Calendar, Heart, AlertCircle, Loader2, Save } from 'lucide-react';
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
import { patientApi } from '@/services/api';

const fallbackTimezones = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Berlin',
  'Asia/Kolkata',
  'Asia/Tokyo',
  'Australia/Sydney',
];

const supportedTimezones: string[] =
  (typeof Intl !== 'undefined' && (Intl as any).supportedValuesOf
    ? (Intl as any).supportedValuesOf('timeZone')
    : fallbackTimezones) || fallbackTimezones;

const defaultTimezone =
  (typeof Intl !== 'undefined' && Intl.DateTimeFormat().resolvedOptions().timeZone) || 'UTC';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ProfileModal({ isOpen, onClose }: ProfileModalProps) {
  const { currentPatient, setCurrentPatient } = usePatientStore();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    date_of_birth: '',
    conditions: '',
    allergies: '',
    timezone: defaultTimezone,
  });

  useEffect(() => {
    if (!currentPatient) return;
    setFormData({
      name: currentPatient.name || '',
      email: currentPatient.email || '',
      phone: currentPatient.phone || '',
      date_of_birth: currentPatient.date_of_birth || '',
      conditions: currentPatient.conditions?.join(', ') || '',
      allergies: currentPatient.allergies?.join(', ') || '',
      timezone: currentPatient.timezone || defaultTimezone,
    });
  }, [currentPatient]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    if (!currentPatient) return;
    setIsSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const nameParts = formData.name.trim().split(' ');
      const first_name = nameParts[0] || '';
      const last_name = nameParts.slice(1).join(' ');
      const payload: any = {
        first_name,
        last_name,
        email: formData.email,
        phone: formData.phone,
        date_of_birth: formData.date_of_birth || undefined,
        conditions: formData.conditions.split(',').map((c) => c.trim()).filter(Boolean),
        allergies: formData.allergies.split(',').map((a) => a.trim()).filter(Boolean),
        timezone: formData.timezone || defaultTimezone,
      };
      const updated = await patientApi.update(currentPatient.id, payload);
      const fullName = [updated?.first_name, updated?.last_name].filter(Boolean).join(' ').trim() || updated.name || updated.email?.split('@')[0] || 'User';
      setCurrentPatient({
        id: updated.id,
        name: fullName,
        email: updated.email,
        phone: updated.phone,
        date_of_birth: updated.date_of_birth,
        timezone: updated.timezone || defaultTimezone,
        conditions: updated.conditions || [],
        allergies: updated.allergies || [],
        notification_preferences: updated.notification_preferences || {},
        created_at: updated.created_at,
        updated_at: updated.updated_at,
        is_active: updated.is_active,
      });
      setSuccess(true);
      setIsEditing(false);
      setTimeout(() => setSuccess(false), 2000);
    } catch (err) {
      console.error('Profile update failed', err);
      setError('Could not save profile. Please try again.');
    } finally {
      setIsSaving(false);
    }
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
          className="w-full max-w-lg mx-4 max-h-[90vh] overflow-auto"
          onClick={(e) => e.stopPropagation()}
        >
          <Card className="border-2">
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <User className="h-5 w-5 text-primary" />
                </div>
                <CardTitle>Profile</CardTitle>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose}>
                <X className="h-5 w-5" />
              </Button>
            </CardHeader>
            
            <CardContent className="space-y-6">
              {/* Avatar Section */}
              <div className="flex items-center gap-4">
                <div className="h-20 w-20 rounded-full bg-primary/10 flex items-center justify-center">
                  <span className="text-3xl font-bold text-primary">
                    {formData.name.charAt(0) || 'U'}
                  </span>
                </div>
                <div>
                  <h3 className="font-semibold text-lg">{formData.name || 'User'}</h3>
                  <p className="text-sm text-muted-foreground">{formData.email}</p>
                </div>
              </div>
              
              {error && (
                <div className="p-3 rounded-md bg-red-50 dark:bg-red-900/20 text-sm text-red-700 dark:text-red-200">
                  {error}
                </div>
              )}
              {success && (
                <div className="p-3 rounded-md bg-green-50 dark:bg-green-900/20 text-sm text-green-700 dark:text-green-200">
                  Profile updated
                </div>
              )}

              {/* Form Fields */}
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium mb-1.5 block flex items-center gap-2">
                    <User className="h-4 w-4" />
                    Full Name
                  </label>
                  <Input
                    name="name"
                    value={formData.name}
                    onChange={handleChange}
                    disabled={!isEditing}
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1.5 block flex items-center gap-2">
                    <Mail className="h-4 w-4" />
                    Email
                  </label>
                  <Input
                    name="email"
                    type="email"
                    value={formData.email}
                    onChange={handleChange}
                    disabled={!isEditing}
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1.5 block flex items-center gap-2">
                    <Phone className="h-4 w-4" />
                    Phone
                  </label>
                  <Input
                    name="phone"
                    value={formData.phone}
                    onChange={handleChange}
                    disabled={!isEditing}
                    placeholder="Enter phone number"
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1.5 block flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    Date of Birth
                  </label>
                  <Input
                    name="date_of_birth"
                    type="date"
                    value={formData.date_of_birth}
                    onChange={handleChange}
                    disabled={!isEditing}
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1.5 block flex items-center gap-2">
                    <AlertCircle className="h-4 w-4" />
                    Timezone
                  </label>
                  <Input
                    name="timezone"
                    value={formData.timezone}
                    onChange={handleChange}
                    disabled={!isEditing}
                    placeholder="Search by city (e.g., America/New_York)"
                    list="timezone-options"
                  />
                  <datalist id="timezone-options">
                    {supportedTimezones.map((tz) => (
                      <option key={tz} value={tz} />
                    ))}
                  </datalist>
                  <p className="text-xs text-muted-foreground mt-1">
                    Start typing your city or region to quickly find the right timezone
                  </p>
                </div>

                <div>
                  <label className="text-sm font-medium mb-1.5 block flex items-center gap-2">
                    <Heart className="h-4 w-4" />
                    Medical Conditions
                  </label>
                  <Input
                    name="conditions"
                    value={formData.conditions}
                    onChange={handleChange}
                    disabled={!isEditing}
                    placeholder="Type 2 Diabetes, Hypertension"
                  />
                  <p className="text-xs text-muted-foreground mt-1">Separate multiple conditions with commas</p>
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1.5 block flex items-center gap-2">
                    <AlertCircle className="h-4 w-4" />
                    Allergies
                  </label>
                  <Input
                    name="allergies"
                    value={formData.allergies}
                    onChange={handleChange}
                    disabled={!isEditing}
                    placeholder="Penicillin, Aspirin"
                  />
                  <p className="text-xs text-muted-foreground mt-1">Separate multiple allergies with commas</p>
                </div>
              </div>
              
              {/* Badges */}
              {currentPatient?.conditions && currentPatient.conditions.length > 0 && (
                <div>
                  <p className="text-sm font-medium mb-2">Current Conditions</p>
                  <div className="flex flex-wrap gap-2">
                    {currentPatient.conditions.map((condition, i) => (
                      <Badge key={i} variant="secondary">{condition}</Badge>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t">
                {isEditing ? (
                  <>
                    <Button variant="outline" onClick={() => setIsEditing(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleSave} disabled={isSaving}>
                      {isSaving ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        <>
                          <Save className="h-4 w-4 mr-2" />
                          Save Changes
                        </>
                      )}
                    </Button>
                  </>
                ) : (
                  <Button onClick={() => setIsEditing(true)}>
                    Edit Profile
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
