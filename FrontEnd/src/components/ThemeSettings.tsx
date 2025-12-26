import React, { useState } from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { useTheme } from '@/hooks/useTheme';
import { Image as ImageIcon, Link as LinkIcon, Palette, Type, RotateCcw, Upload, CheckCircle2, Sun, Moon } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';

interface ThemeSettingsProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

const PRESET_THEMES = [
    { name: 'Midnight', primary: '199 89% 48%', accent: '346 84% 61%', bg: '/chat-bg.png' },
    { name: 'Ocean', primary: '210 100% 50%', accent: '180 100% 50%', bg: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200' },
    { name: 'Nature', primary: '142 76% 36%', accent: '38 92% 50%', bg: 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1200' },
    { name: 'Desert', primary: '24 100% 50%', accent: '346 84% 61%', bg: 'https://images.unsplash.com/photo-1472214103451-9374bd1c798e?auto=format&fit=crop&w=1200' },
    { name: 'Cyber', primary: '280 100% 70%', accent: '320 100% 60%', bg: 'https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=1200' },
    { name: 'Aurora', primary: '160 100% 50%', accent: '200 100% 50%', bg: 'https://images.unsplash.com/photo-1483347756197-71ef80e95f73?auto=format&fit=crop&w=1200' },
];

const MAX_FILE_SIZE = 1 * 1024 * 1024; // 1MB

export function ThemeSettings({ open, onOpenChange }: ThemeSettingsProps) {
    const { settings, updateSettings, addCustomTheme, resetTheme } = useTheme();
    const [imageUrl, setImageUrl] = useState(settings.backgroundImage);
    const { toast } = useToast();

    const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            if (file.size > MAX_FILE_SIZE) {
                toast({
                    title: "File too large",
                    description: "Please select an image smaller than 1MB to ensure it can be saved.",
                    variant: "destructive"
                });
                return;
            }

            const reader = new FileReader();
            reader.onloadend = () => {
                const base64String = reader.result as string;
                const newTheme = {
                    name: `Custom ${(settings.customThemes?.length || 0) + 1}`,
                    primary: settings.primaryColor,
                    accent: settings.accentColor,
                    bg: base64String
                };
                addCustomTheme(newTheme);
                updateSettings({ backgroundImage: base64String, themeName: newTheme.name });
                setImageUrl(base64String);
                toast({
                    title: "Theme added",
                    description: "Your custom background has been saved.",
                });
            };
            reader.readAsDataURL(file);
        }
    };

    const handleUrlSubmit = () => {
        if (!imageUrl) return;
        const newTheme = {
            name: `Custom ${(settings.customThemes?.length || 0) + 1}`,
            primary: settings.primaryColor,
            accent: settings.accentColor,
            bg: imageUrl
        };
        addCustomTheme(newTheme);
        updateSettings({ backgroundImage: imageUrl, themeName: newTheme.name });
        toast({
            title: "Theme added",
            description: "The background URL has been saved to your themes.",
        });
    };

    const handleHueChange = (val: number[]) => {
        const hue = val[0];
        updateSettings({ primaryColor: `${hue} 89% 48%` });
    };

    const handleAccentHueChange = (val: number[]) => {
        const hue = val[0];
        updateSettings({ accentColor: `${hue} 84% 61%` });
    };

    const handleFontSizeChange = (val: number[]) => {
        updateSettings({ fontSize: `${val[0]}px` });
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[900px] w-[95vw] md:w-full bg-card border-border shadow-2xl rounded-[1.5rem] md:rounded-[2rem] overflow-hidden p-0 gap-0 max-h-[90vh] flex flex-col">
                <Tabs defaultValue="background" className="w-full flex-1 flex flex-col min-h-0">
                    <div className="flex flex-col md:flex-row flex-1 min-h-0">
                        {/* Sidebar for Tabs */}
                        <div className="w-full md:w-64 border-b md:border-b-0 md:border-r border-border bg-muted/30 p-4 md:p-6 flex flex-col gap-4 md:gap-6 shrink-0">
                            <div className="flex flex-row md:flex-col items-center md:items-start justify-start gap-4">
                                <div className="flex items-center gap-2">
                                    <DialogTitle className="text-lg md:text-xl font-bold flex items-center gap-2 mb-0 md:mb-1">
                                        <Palette className="w-5 h-5 text-primary" />
                                        Appearance
                                    </DialogTitle>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={resetTheme}
                                        className="md:hidden p-2 h-8 w-8 rounded-lg text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors"
                                        title="Reset Defaults"
                                    >
                                        <RotateCcw className="w-4 h-4" />
                                    </Button>
                                    <p className="hidden md:block text-xs text-muted-foreground">Customize your workspace</p>
                                </div>
                            </div>

                            <div className="w-full flex-1">
                                <TabsList className="flex flex-row md:flex-col h-auto bg-transparent p-0 gap-1 md:gap-2 overflow-x-auto scrollbar-hide">
                                    <TabsTrigger
                                        value="background"
                                        className="flex-1 md:w-full justify-center md:justify-start gap-2 md:gap-3 px-3 md:px-4 py-2 md:py-3 rounded-lg md:rounded-xl data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all text-xs md:text-sm"
                                    >
                                        <ImageIcon className="w-3.5 h-3.5 md:w-4 md:h-4" />
                                        <span className="whitespace-nowrap">Background</span>
                                    </TabsTrigger>
                                    <TabsTrigger
                                        value="appearance"
                                        className="flex-1 md:w-full justify-center md:justify-start gap-2 md:gap-3 px-3 md:px-4 py-2 md:py-3 rounded-lg md:rounded-xl data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all text-xs md:text-sm"
                                    >
                                        <Palette className="w-3.5 h-3.5 md:w-4 md:h-4" />
                                        <span className="whitespace-nowrap">Colors</span>
                                    </TabsTrigger>
                                    <TabsTrigger
                                        value="fonts"
                                        className="flex-1 md:w-full justify-center md:justify-start gap-2 md:gap-3 px-3 md:px-4 py-2 md:py-3 rounded-lg md:rounded-xl data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all text-xs md:text-sm"
                                    >
                                        <Type className="w-3.5 h-3.5 md:w-4 md:h-4" />
                                        <span className="whitespace-nowrap">Fonts</span>
                                    </TabsTrigger>
                                </TabsList>
                            </div>

                            <div className="hidden md:block mt-auto pt-6 border-t border-border">
                                <Button
                                    variant="ghost"
                                    onClick={resetTheme}
                                    className="w-full justify-start gap-3 px-4 py-3 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted"
                                >
                                    <RotateCcw className="w-4 h-4" />
                                    Reset Defaults
                                </Button>
                            </div>
                        </div>

                        {/* Main Content Area */}
                        <div className="flex-1 flex flex-col min-w-0 min-h-0">
                            <div className="flex-1 overflow-y-auto p-4 md:p-8 scrollbar-premium">
                                <TabsContent value="background" className="mt-0 space-y-6 md:space-y-8">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
                                        {/* Left: Theme Selection */}
                                        <div className="space-y-4">
                                            <Label className="text-[10px] md:text-sm font-bold uppercase tracking-wider text-muted-foreground">Select a Theme</Label>
                                            <div className="grid grid-cols-2 gap-3 md:gap-4">
                                                {[...PRESET_THEMES, ...(settings.customThemes || [])].map((t) => (
                                                    <button
                                                        key={t.name}
                                                        onClick={() => updateSettings({
                                                            themeName: t.name,
                                                            primaryColor: t.primary,
                                                            accentColor: t.accent,
                                                            backgroundImage: t.bg
                                                        })}
                                                        className={`group relative aspect-video rounded-2xl overflow-hidden border-2 transition-all duration-300 ${settings.themeName === t.name
                                                            ? 'border-primary ring-4 ring-primary/20 shadow-xl scale-[1.02]'
                                                            : 'border-transparent hover:border-border hover:scale-[1.02]'
                                                            }`}
                                                    >
                                                        <img src={t.bg} alt={t.name} className="w-full h-full object-cover brightness-75 group-hover:brightness-90 transition-all duration-500" />
                                                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-60" />
                                                        <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between">
                                                            <span className="text-white font-semibold text-sm truncate pr-2">
                                                                {t.name}
                                                            </span>
                                                            {settings.themeName === t.name && (
                                                                <CheckCircle2 className="w-4 h-4 text-primary-foreground fill-primary shrink-0" />
                                                            )}
                                                        </div>
                                                    </button>
                                                ))}
                                            </div>
                                        </div>

                                        {/* Right: Add New */}
                                        <div className="space-y-6 md:space-y-8 md:border-l border-border md:pl-8">
                                            <div className="space-y-4">
                                                <Label className="text-[10px] md:text-sm font-bold uppercase tracking-wider text-muted-foreground">Custom Background</Label>

                                                <div className="space-y-6">
                                                    {/* Upload Box */}
                                                    <div className="relative group">
                                                        <Input
                                                            type="file"
                                                            accept="image/*"
                                                            onChange={handleImageUpload}
                                                            className="hidden"
                                                            id="bg-upload"
                                                        />
                                                        <Label
                                                            htmlFor="bg-upload"
                                                            className="flex flex-col items-center justify-center gap-4 aspect-video rounded-2xl border-2 border-dashed border-border group-hover:border-primary group-hover:bg-primary/5 cursor-pointer transition-all duration-300"
                                                        >
                                                            <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                                                                <Upload className="w-6 h-6" />
                                                            </div>
                                                            <div className="text-center">
                                                                <p className="font-semibold text-sm">Upload Image</p>
                                                                <p className="text-xs text-muted-foreground mt-1">PNG, JPG up to 5MB</p>
                                                            </div>
                                                        </Label>
                                                    </div>

                                                    <div className="relative">
                                                        <div className="absolute inset-0 flex items-center">
                                                            <span className="w-full border-t border-border" />
                                                        </div>
                                                        <div className="relative flex justify-center text-xs uppercase">
                                                            <span className="bg-card px-2 text-muted-foreground font-medium">Or use URL</span>
                                                        </div>
                                                    </div>

                                                    <div className="flex gap-2">
                                                        <Input
                                                            value={imageUrl}
                                                            onChange={(e) => setImageUrl(e.target.value)}
                                                            placeholder="https://images.unsplash.com/..."
                                                            className="rounded-xl bg-muted/30 border-border h-11"
                                                        />
                                                        <Button onClick={handleUrlSubmit} size="icon" className="rounded-xl shrink-0 h-11 w-11">
                                                            <LinkIcon className="w-4 h-4" />
                                                        </Button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </TabsContent>

                                <TabsContent value="appearance" className="mt-0 space-y-8 max-w-2xl mx-auto">
                                    <div className="space-y-8">
                                        <div className="space-y-4">
                                            <Label className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Theme Mode</Label>
                                            <div className="grid grid-cols-2 gap-4">
                                                <button
                                                    onClick={() => updateSettings({ mode: 'light', fontColor: '240 10% 3.9%' })}
                                                    className={`flex items-center justify-center gap-3 p-4 rounded-2xl border-2 transition-all ${settings.mode === 'light'
                                                        ? 'border-primary bg-primary/5 text-primary'
                                                        : 'border-border hover:border-primary/50 text-muted-foreground'
                                                        }`}
                                                >
                                                    <Sun className="w-5 h-5" />
                                                    <span className="font-semibold">Light Mode</span>
                                                </button>
                                                <button
                                                    onClick={() => updateSettings({ mode: 'dark', fontColor: '0 0% 95%' })}
                                                    className={`flex items-center justify-center gap-3 p-4 rounded-2xl border-2 transition-all ${settings.mode === 'dark'
                                                        ? 'border-primary bg-primary/5 text-primary'
                                                        : 'border-border hover:border-primary/50 text-muted-foreground'
                                                        }`}
                                                >
                                                    <Moon className="w-5 h-5" />
                                                    <span className="font-semibold">Dark Mode</span>
                                                </button>
                                            </div>
                                        </div>

                                        <div className="space-y-8">
                                            <div className="space-y-4">
                                                <div className="flex justify-between items-center">
                                                    <Label className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Primary Color</Label>
                                                    <span className="px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-mono font-bold">
                                                        {settings.primaryColor.split(' ')[0]}° Hue
                                                    </span>
                                                </div>
                                                <div className="p-6 rounded-2xl bg-muted/30 border border-border space-y-6">
                                                    <Slider
                                                        defaultValue={[parseInt(settings.primaryColor.split(' ')[0])]}
                                                        max={360}
                                                        step={1}
                                                        onValueCommit={handleHueChange}
                                                    />
                                                    <div
                                                        className="h-12 w-full rounded-xl shadow-inner border border-white/10"
                                                        style={{ background: `hsl(${settings.primaryColor})` }}
                                                    />
                                                </div>
                                            </div>

                                            <div className="space-y-4">
                                                <div className="flex justify-between items-center">
                                                    <Label className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Accent Color</Label>
                                                    <span className="px-3 py-1 rounded-full bg-accent/10 text-accent text-xs font-mono font-bold" style={{ color: `hsl(${settings.accentColor})`, backgroundColor: `hsl(${settings.accentColor} / 0.1)` }}>
                                                        {settings.accentColor.split(' ')[0]}° Hue
                                                    </span>
                                                </div>
                                                <div className="p-6 rounded-2xl bg-muted/30 border border-border space-y-6">
                                                    <Slider
                                                        defaultValue={[parseInt(settings.accentColor.split(' ')[0])]}
                                                        max={360}
                                                        step={1}
                                                        onValueCommit={handleAccentHueChange}
                                                    />
                                                    <div
                                                        className="h-12 w-full rounded-xl shadow-inner border border-white/10"
                                                        style={{ background: `hsl(${settings.accentColor})` }}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </TabsContent>

                                <TabsContent value="fonts" className="mt-0 space-y-8 max-w-2xl mx-auto">
                                    <div className="space-y-6">
                                        <div className="flex justify-between items-center">
                                            <Label className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Font Size</Label>
                                            <span className="px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-mono font-bold">
                                                {settings.fontSize}
                                            </span>
                                        </div>
                                        <div className="p-8 rounded-2xl bg-muted/30 border border-border space-y-8">
                                            <Slider
                                                defaultValue={[parseInt(settings.fontSize)]}
                                                min={12}
                                                max={24}
                                                step={1}
                                                onValueCommit={handleFontSizeChange}
                                            />
                                            <div className="p-8 rounded-xl bg-card border border-border shadow-sm">
                                                <p style={{ fontSize: settings.fontSize }} className="text-foreground leading-relaxed">
                                                    The quick brown fox jumps over the lazy dog.
                                                    <br />
                                                    <span className="text-muted-foreground text-[0.8em]">This is a preview of how your chat messages will look.</span>
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </TabsContent>
                            </div>

                            <div className="p-4 md:p-6 border-t border-border bg-muted/10 flex justify-end">
                                <Button onClick={() => onOpenChange(false)} className="rounded-xl w-full md:w-auto md:px-12 h-11 font-bold shadow-lg shadow-primary/20">
                                    Done
                                </Button>
                            </div>
                        </div>
                    </div>
                </Tabs>
            </DialogContent>
        </Dialog >
    );
}
