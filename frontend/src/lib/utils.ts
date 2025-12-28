import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTime(time: string): string {
  const [hours, minutes] = time.split(':').map(Number);
  const period = hours >= 12 ? 'PM' : 'AM';
  const displayHours = hours % 12 || 12;
  return `${displayHours}:${minutes.toString().padStart(2, '0')} ${period}`;
}

export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export function formatRelativeTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffMins = Math.round(diffMs / 60000);
  const diffHours = Math.round(diffMins / 60);
  const diffDays = Math.round(diffHours / 24);

  if (Math.abs(diffMins) < 60) {
    if (diffMins === 0) return 'now';
    return diffMins > 0 ? `in ${diffMins} minutes` : `${Math.abs(diffMins)} minutes ago`;
  }
  if (Math.abs(diffHours) < 24) {
    return diffHours > 0 ? `in ${diffHours} hours` : `${Math.abs(diffHours)} hours ago`;
  }
  return diffDays > 0 ? `in ${diffDays} days` : `${Math.abs(diffDays)} days ago`;
}

export function getAdherenceColor(rate: number): string {
  if (rate >= 90) return 'text-green-500';
  if (rate >= 75) return 'text-lime-500';
  if (rate >= 50) return 'text-yellow-500';
  return 'text-red-500';
}

export function getAdherenceBgColor(rate: number): string {
  if (rate >= 90) return 'bg-green-500/10';
  if (rate >= 75) return 'bg-lime-500/10';
  if (rate >= 50) return 'bg-yellow-500/10';
  return 'bg-red-500/10';
}

export function getSeverityColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'contraindicated':
      return 'text-red-600 bg-red-100 dark:bg-red-900/30';
    case 'major':
      return 'text-orange-600 bg-orange-100 dark:bg-orange-900/30';
    case 'moderate':
      return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30';
    case 'minor':
      return 'text-blue-600 bg-blue-100 dark:bg-blue-900/30';
    default:
      return 'text-gray-600 bg-gray-100 dark:bg-gray-900/30';
  }
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '...';
}
