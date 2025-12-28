import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertCircle,
  Activity,
  Clock,
  ThermometerSun,
  Loader2,
  CheckCircle2,
  ChevronRight,
} from 'lucide-react';
import { format } from 'date-fns';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Input,
  Badge,
  ScrollArea,
} from '@/components/ui';
import { cn, getSeverityColor } from '@/lib/utils';
import { usePatientStore } from '@/stores/patientStore';
import {
  useSymptoms,
  useCreateSymptom,
} from '@/hooks/useAdherence';
import { useSendMessage } from '@/hooks/useChat';
import { appendChatSession } from '@/lib/chatSession';

const REQUIRED_MSG = 'Please select a symptom and severity before submitting.';

const COMMON_SYMPTOMS = [
  { name: 'Headache', icon: '🤕' },
  { name: 'Nausea', icon: '🤢' },
  { name: 'Dizziness', icon: '😵' },
  { name: 'Fatigue', icon: '😴' },
  { name: 'Stomach upset', icon: '🤮' },
  { name: 'Muscle pain', icon: '💪' },
  { name: 'Drowsiness', icon: '😪' },
  { name: 'Dry mouth', icon: '👄' },
  { name: 'Loss of appetite', icon: '🍽️' },
  { name: 'Constipation', icon: '🚽' },
  { name: 'Rash', icon: '🔴' },
  { name: 'Sweating', icon: '💦' },
];

const SEVERITY_LEVELS = [
  { value: 'mild', label: 'Mild', color: 'bg-green-500' },
  { value: 'moderate', label: 'Moderate', color: 'bg-yellow-500' },
  { value: 'severe', label: 'Severe', color: 'bg-red-500' },
];

export default function SymptomReport() {
  const { currentPatient, setActiveTab } = usePatientStore();
  const patientId = currentPatient?.id || null;
  
  const { data: symptoms, isLoading } = useSymptoms(patientId);
  const createSymptom = useCreateSymptom(patientId);
  const sendMessage = useSendMessage(patientId);

  const [selectedSymptom, setSelectedSymptom] = useState<string>('');
  const [customSymptom, setCustomSymptom] = useState('');
  const [severity, setSeverity] = useState<string>('');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const appendChat = (userId: number, newMessages: { role: 'user' | 'assistant'; content: string }[]) => {
    appendChatSession(userId, newMessages);
  };

  const handleSubmit = async () => {
    const symptomName = selectedSymptom || customSymptom;
    if (!symptomName || !severity || !patientId) {
      setFormError(REQUIRED_MSG);
      return;
    }
    setFormError(null);

    setIsSubmitting(true);
    try {
      await createSymptom.mutateAsync({
        symptom_name: symptomName,
        severity,
        notes: notes || undefined,
        reported_at: new Date().toISOString(),
      });

      // Send the report into chat so the assistant can respond
      if (patientId) {
        const chatText = `I just reported a symptom: ${symptomName} (severity: ${severity}). ${notes ? `Notes: ${notes}` : ''}`.trim();
        try {
          const response = await sendMessage.mutateAsync({
            message: chatText,
            context: {
              type: 'symptom_report',
              symptom: symptomName,
              severity,
            },
          });

          appendChat(patientId, [
            { role: 'user', content: chatText },
            { role: 'assistant', content: response.response || 'Thanks, I will review this symptom.' },
          ]);
        } catch (err) {
          appendChat(patientId, [
            { role: 'user', content: chatText },
            { role: 'assistant', content: 'I received your symptom report. I will review and assist shortly.' },
          ]);
        }
      }
      
      // Reset form
      setSelectedSymptom('');
      setCustomSymptom('');
      setSeverity('');
      setNotes('');
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 3000);

      // Switch to AI Chat to review
      setActiveTab('chat');
    } finally {
      setIsSubmitting(false);
    }
  };

  const recentSymptoms = symptoms?.slice(0, 5) || [];

  return (
    <div className="space-y-6">
      {/* Report Form */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-primary" />
            <CardTitle>Report a Symptom</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Success Message */}
          {showSuccess && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="p-4 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center gap-3"
            >
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              <div>
                <p className="font-medium text-green-800 dark:text-green-200">
                  Symptom reported successfully
                </p>
                <p className="text-sm text-green-600 dark:text-green-400">
                  Your healthcare team has been notified.
                </p>
              </div>
            </motion.div>
          )}

          {/* Common Symptoms */}
          <div>
            <label className="text-sm font-medium mb-3 block">
              Select a symptom or type your own
            </label>
            {formError && (
              <div className="mb-3 text-sm text-red-600 dark:text-red-300">
                {formError}
              </div>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
              {COMMON_SYMPTOMS.map((symptom) => (
                <Button
                  key={symptom.name}
                  variant={selectedSymptom === symptom.name ? 'default' : 'outline'}
                  size="sm"
                  className="justify-start"
                  onClick={() => {
                    setSelectedSymptom(symptom.name);
                    setCustomSymptom('');
                  }}
                >
                  <span className="mr-2">{symptom.icon}</span>
                  {symptom.name}
                </Button>
              ))}
            </div>
            <div className="relative">
              <Input
                placeholder="Or describe your symptom..."
                value={customSymptom}
                onChange={(e) => {
                  setCustomSymptom(e.target.value);
                  setSelectedSymptom('');
                }}
              />
            </div>
          </div>

          {/* Severity */}
          <div>
            <label className="text-sm font-medium mb-3 block">
              How severe is it?
            </label>
            <div className="flex gap-3">
              {SEVERITY_LEVELS.map((level) => (
                <Button
                  key={level.value}
                  variant={severity === level.value ? 'default' : 'outline'}
                  className={cn(
                    "flex-1",
                    severity === level.value && level.value === 'mild' && "bg-green-600 hover:bg-green-700",
                    severity === level.value && level.value === 'moderate' && "bg-yellow-600 hover:bg-yellow-700",
                    severity === level.value && level.value === 'severe' && "bg-red-600 hover:bg-red-700"
                  )}
                  onClick={() => setSeverity(level.value)}
                >
                  <div className={cn("w-2 h-2 rounded-full mr-2", level.color)} />
                  {level.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="text-sm font-medium mb-3 block">
              Additional notes (optional)
            </label>
            <textarea
              className={cn(
                "w-full min-h-[100px] rounded-md border border-input bg-transparent px-3 py-2 text-sm",
                "focus:outline-none focus:ring-2 focus:ring-ring"
              )}
              placeholder="When did it start? Any patterns? Related to a specific medication?"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          {/* Submit */}
          <Button
            className="w-full"
            disabled={(!selectedSymptom && !customSymptom) || !severity || isSubmitting}
            onClick={handleSubmit}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Submitting...
              </>
            ) : (
              <>
                <Activity className="h-4 w-4 mr-2" />
                Submit Report
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Recent Symptoms */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Recent Reports</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : recentSymptoms.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <ThermometerSun className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>No symptoms reported yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentSymptoms.map((symptom, index) => (
                <motion.div
                  key={symptom.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="p-4 rounded-lg border bg-card flex items-start justify-between"
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        "w-3 h-3 rounded-full mt-1.5",
                        symptom.severity === 'mild' && "bg-green-500",
                        symptom.severity === 'moderate' && "bg-yellow-500",
                        symptom.severity === 'severe' && "bg-red-500"
                      )}
                    />
                    <div>
                      <h4 className="font-medium">{symptom.symptom_name}</h4>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge
                          variant={
                            symptom.severity === 'mild'
                              ? 'success'
                              : symptom.severity === 'moderate'
                              ? 'warning'
                              : 'destructive'
                          }
                        >
                          {symptom.severity}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {format(new Date(symptom.reported_at), 'MMM d, yyyy h:mm a')}
                        </span>
                      </div>
                      {symptom.notes && (
                        <p className="text-sm text-muted-foreground mt-2">
                          {symptom.notes}
                        </p>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}

              {symptoms && symptoms.length > 5 && (
                <Button variant="ghost" className="w-full">
                  View all reports
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
