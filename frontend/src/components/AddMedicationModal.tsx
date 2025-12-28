import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Pill, Search, Loader2, AlertCircle, ChevronDown } from 'lucide-react';
import {
  Button,
  Input,
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui';
import { useCreateMedication, useMedications } from '@/hooks/useMedications';
import { usePatientStore } from '@/stores/patientStore';
import { medicationApi } from '@/services/api';
import { cn } from '@/lib/utils';

interface DrugSearchResult {
  name: string;
  generic_name: string;
  drug_class: string;
}

interface AddMedicationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AddMedicationModal({ isOpen, onClose }: AddMedicationModalProps) {
  const { currentPatient } = usePatientStore();
  const createMedication = useCreateMedication();
  const { data: existingMedications } = useMedications(currentPatient?.id || null);
  
  const [formData, setFormData] = useState({
    name: '',
    dosage: '',
    frequency: 'once daily',
    instructions: '',
    purpose: '',
    with_food: false,
    custom_times: '',
  });
  
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<DrugSearchResult[]>([]);
  const [allDrugs, setAllDrugs] = useState<DrugSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false); // New state for submission status
  const dropdownRef = useRef<HTMLDivElement>(null);

  const frequencyOptions = [
    'once daily',
    'twice daily',
    'three times daily',
    'four times daily',
    'every 4 hours',
    'every 6 hours',
    'every 8 hours',
    'every 12 hours',
    'once weekly',
    'as needed',
  ];

  // Search for drugs as user types — prefer local filtering of preloaded list for responsiveness
  useEffect(() => {
    setIsSearching(true);
    const debounceTimer = setTimeout(async () => {
      const q = (searchQuery || '').trim().toLowerCase();

      // If we have a preloaded master list, filter locally
      if (allDrugs && allDrugs.length > 0) {
        if (!q) {
          setSearchResults(allDrugs.slice(0, 1000));
          setIsSearching(false);
          return;
        }

        const filtered = allDrugs.filter((d) =>
          (d.name || '').toLowerCase().includes(q) || (d.generic_name || '').toLowerCase().includes(q)
        );
        setSearchResults(filtered.slice(0, 1000));
        setIsSearching(false);
        return;
      }

      // Fallback: query backend with a larger limit
      try {
        const results = await medicationApi.searchDrugs(searchQuery, 1000);
        setSearchResults(results);
      } catch (error) {
        console.error('Error searching drugs:', error);
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(debounceTimer);
  }, [searchQuery, allDrugs]);

  // Load initial drugs when modal opens
  useEffect(() => {
    if (isOpen) {
      // Try to preload a large list of drugs for local filtering (fast UX)
      (async () => {
        try {
          const results = await medicationApi.searchDrugs('', 100000);
          if (results && results.length > 0) {
            setAllDrugs(results);
            setSearchResults(results.slice(0, 1000));
            return;
          }
        } catch (err) {
          // ignore and fallback to small search
        }

        // Fallback to server default small list
        try {
          const fallback = await medicationApi.searchDrugs('');
          setSearchResults(fallback);
        } catch (err) {
          console.error('Failed to load initial drug list', err);
        }
      })();
    }
  }, [isOpen]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Check if drug is already active
  const isActiveDrug = (drugName: string): boolean => {
    if (!existingMedications) return false;
    return existingMedications.some(
      med => med.is_active && med.name.toLowerCase() === drugName.toLowerCase()
    );
  };

  const handleSelectDrug = (drug: DrugSearchResult) => {
    if (isActiveDrug(drug.name)) {
      setErrors(prev => ({ ...prev, name: `${drug.name} is already in your active medications` }));
      return;
    }
    
    setFormData(prev => ({ ...prev, name: drug.name }));
    setSearchQuery(drug.name);
    setShowDropdown(false);
    setErrors(prev => ({ ...prev, name: '' }));
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value);
    setFormData(prev => ({ ...prev, name: value }));
    setShowDropdown(true);
    
    // Clear error when typing
    if (errors.name) {
      setErrors(prev => ({ ...prev, name: '' }));
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    const newValue = type === 'checkbox' ? (e.target as HTMLInputElement).checked : value;
    setFormData(prev => ({ ...prev, [name]: newValue }));
    
    // Clear error for this field
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const validate = () => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.name.trim()) {
      newErrors.name = 'Medication name is required';
    } else if (isActiveDrug(formData.name)) {
      newErrors.name = `${formData.name} is already in your active medications`;
    }
    
    if (!formData.dosage.trim()) {
      newErrors.dosage = 'Dosage is required';
    }

    if (formData.custom_times) {
      const times = formData.custom_times.split(',').map((t) => t.trim()).filter(Boolean);
      const invalid = times.some((t) => !/^\d{2}:\d{2}$/.test(t));
      if (invalid) {
        newErrors.custom_times = 'Use HH:MM format, separated by commas';
      }
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validate() || !currentPatient?.id) return;
    
    try {
      setIsSubmitting(true); // Set submitting state to true
      await createMedication.mutateAsync({ 
        patientId: currentPatient.id,
        medication: {
          name: formData.name,
          dosage: formData.dosage,
          frequency: formData.frequency,
          instructions: formData.instructions || `Take ${formData.dosage} ${formData.frequency}`,
          purpose: formData.purpose,
          with_food: formData.with_food,
          is_active: true,
        },
        customTimes: formData.custom_times
          ? formData.custom_times.split(',').map((t) => t.trim()).filter(Boolean)
          : undefined,
      });
      
      // Reset form and close modal
      setFormData({
        name: '',
        dosage: '',
        frequency: 'once daily',
        instructions: '',
        purpose: '',
        with_food: false,
        custom_times: '',
      });
      setSearchQuery('');
      onClose();
      setIsSubmitting(false); // Reset submitting state
    } catch (error) {
      console.error('Failed to add medication:', error);
      setErrors({ submit: 'Failed to add medication. Please try again.' });
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
          className="w-full max-w-lg mx-4"
          onClick={(e) => e.stopPropagation()}
        >
          <Card className="border-2">
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <Pill className="h-5 w-5 text-primary" />
                </div>
                <CardTitle>Add New Medication</CardTitle>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose}>
                <X className="h-5 w-5" />
              </Button>
            </CardHeader>
            
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Medication Name with Search Dropdown */}
                <div ref={dropdownRef} className="relative">
                  <label className="text-sm font-medium mb-1.5 block">
                    Medication Name *
                  </label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      name="name"
                      placeholder="Search for medication..."
                      value={searchQuery}
                      onChange={handleSearchChange}
                      onFocus={() => setShowDropdown(true)}
                      className={cn("pl-10 pr-10 bg-transparent text-foreground placeholder:text-muted-foreground", errors.name ? 'border-red-500' : '')}
                    />
                    {isSearching ? (
                      <Loader2 className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
                    ) : (
                      <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                  
                  {/* Search Dropdown */}
                  <AnimatePresence>
                    {showDropdown && (
                      <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="absolute z-50 w-full mt-1 max-h-60 overflow-auto rounded-md border bg-popover shadow-lg"
                      >
                        {searchResults.length === 0 ? (
                          <div className="p-3 text-sm text-muted-foreground">No results. Try a different search term.</div>
                        ) : (
                          searchResults.map((drug, idx) => {
                            const isActive = isActiveDrug(drug.name);
                            return (
                              <div
                                key={idx}
                                onClick={() => !isActive && handleSelectDrug(drug)}
                                className={cn(
                                  "p-3 border-b last:border-0 cursor-pointer",
                                  isActive
                                    ? "bg-muted/50 cursor-not-allowed opacity-60"
                                    : "hover:bg-muted/50"
                                )}
                              >
                                <div className="flex items-center justify-between">
                                  <span className="font-medium">{drug.name}</span>
                                  {isActive && (
                                    <Badge variant="secondary" className="text-xs">
                                      Already active
                                    </Badge>
                                  )}
                                </div>
                                <p className="text-xs text-muted-foreground">{drug.drug_class}</p>
                              </div>
                            );
                          })
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                  
                  {errors.name && (
                    <p className="text-sm text-red-500 mt-1 flex items-center gap-1">
                      <AlertCircle className="h-3 w-3" />
                      {errors.name}
                    </p>
                  )}
                </div>
                
                {/* Dosage */}
                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    Dosage *
                  </label>
                  <Input
                    name="dosage"
                    placeholder="e.g., 500mg"
                    value={formData.dosage}
                    onChange={handleChange}
                    className={cn('bg-transparent text-foreground placeholder:text-muted-foreground', errors.dosage ? 'border-red-500' : '')}
                  />
                  {errors.dosage && (
                    <p className="text-sm text-red-500 mt-1">{errors.dosage}</p>
                  )}
                </div>

                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    Custom dose times (HH:MM, comma separated)
                  </label>
                  <Input
                    name="custom_times"
                    placeholder="08:00, 14:00, 20:00"
                    value={formData.custom_times}
                    onChange={handleChange}
                    className={cn('bg-transparent text-foreground placeholder:text-muted-foreground', errors.custom_times ? 'border-red-500' : '')}
                  />
                  {errors.custom_times && (
                    <div className="text-xs text-red-500 mt-1">{errors.custom_times}</div>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">
                    Optional. If empty, we auto-generate times between wake and sleep.
                  </p>
                </div>
                
                {/* Frequency */}
                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    Frequency
                  </label>
                  <select
                    name="frequency"
                    value={formData.frequency}
                    onChange={handleChange}
                    className="w-full h-10 px-3 rounded-md border border-input bg-transparent text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {frequencyOptions.map((freq) => (
                      <option key={freq} value={freq}>
                        {freq.charAt(0).toUpperCase() + freq.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>
                
                {/* Purpose */}
                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    Purpose / Condition
                  </label>
                  <Input
                    name="purpose"
                    placeholder="e.g., Type 2 Diabetes"
                    value={formData.purpose}
                    onChange={handleChange}
                    className="bg-transparent text-foreground placeholder:text-muted-foreground"
                  />
                </div>
                
                {/* Instructions */}
                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    Special Instructions
                  </label>
                  <textarea
                    name="instructions"
                    placeholder="Any special instructions for taking this medication..."
                    value={formData.instructions}
                    onChange={handleChange}
                    rows={2}
                    className="w-full px-3 py-2 rounded-md border border-input bg-transparent text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
                  />
                </div>
                
                {/* With Food */}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="with_food"
                    name="with_food"
                    checked={formData.with_food}
                    onChange={handleChange}
                    className="h-4 w-4 rounded border-input bg-transparent"
                  />
                  <label htmlFor="with_food" className="text-sm">
                    Take with food
                  </label>
                </div>
                
                {/* Error message */}
                {errors.submit && (
                  <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
                    <p className="text-sm text-red-600 dark:text-red-400">{errors.submit}</p>
                  </div>
                )}
                
                {/* Actions */}
                <div className="flex justify-end gap-3 pt-4 border-t">
                  <Button type="button" variant="outline" onClick={onClose}>
                    Cancel
                  </Button>
                    <Button
                      type="submit"
                      disabled={createMedication.isLoading || isSubmitting} // Disable button while loading
                  >
                      {createMedication.isLoading || isSubmitting ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Adding...
                      </>
                    ) : (
                      <>
                        <Pill className="h-4 w-4 mr-2" />
                        Add Medication
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

