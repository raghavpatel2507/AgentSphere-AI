import React, { createContext, useContext, useEffect, useState } from 'react';

interface CustomTheme {
    name: string;
    primary: string;
    accent: string;
    bg: string;
}

interface ThemeSettings {
    mode: 'light' | 'dark';
    backgroundImage: string;
    primaryColor: string;
    accentColor: string;
    fontColor: string;
    fontSize: string;
    themeName: string;
    customThemes: CustomTheme[];
}

interface ThemeContextType {
    settings: ThemeSettings;
    updateSettings: (newSettings: Partial<ThemeSettings>) => void;
    addCustomTheme: (theme: CustomTheme) => void;
    resetTheme: () => void;
}

const defaultSettings: ThemeSettings = {
    mode: 'dark',
    backgroundImage: '/chat-bg.png',
    primaryColor: '199 89% 48%', // Default primary color
    accentColor: '346 84% 61%', // Default accent color (pinkish)
    fontColor: '0 0% 95%',
    fontSize: '16px',
    themeName: 'Default',
    customThemes: [],
};

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [settings, setSettings] = useState<ThemeSettings>(() => {
        const saved = localStorage.getItem('chat-theme-settings');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                return { ...defaultSettings, ...parsed };
            } catch (e) {
                console.error('Error parsing theme settings:', e);
                return defaultSettings;
            }
        }
        return defaultSettings;
    });

    useEffect(() => {
        const timeoutId = setTimeout(() => {
            try {
                localStorage.setItem('chat-theme-settings', JSON.stringify(settings));
            } catch (e) {
                if (e instanceof DOMException && e.name === 'QuotaExceededError') {
                    console.error('Theme settings too large to save to localStorage');
                } else {
                    console.error('Error saving theme settings:', e);
                }
            }
        }, 500); // Debounce by 500ms

        applyTheme(settings);

        return () => clearTimeout(timeoutId);
    }, [settings]);

    const applyTheme = (s: ThemeSettings) => {
        const root = document.documentElement;

        // Handle Dark/Light Mode
        if (s.mode === 'dark') {
            root.classList.add('dark');
        } else {
            root.classList.remove('dark');
        }

        root.style.setProperty('--primary', s.primaryColor);
        root.style.setProperty('--accent', s.accentColor);
        root.style.setProperty('--foreground', s.fontColor);
        root.style.setProperty('--chat-font-size', s.fontSize);
        root.style.setProperty('--chat-bg-image', `url("${s.backgroundImage}")`);
    };

    const updateSettings = (newSettings: Partial<ThemeSettings>) => {
        setSettings((prev) => ({ ...prev, ...newSettings }));
    };

    const addCustomTheme = (theme: CustomTheme) => {
        setSettings((prev) => ({
            ...prev,
            customThemes: [theme, ...prev.customThemes].slice(0, 10), // Keep last 10 custom themes
        }));
    };

    const resetTheme = () => {
        setSettings(defaultSettings);
    };

    return (
        <ThemeContext.Provider value={{ settings, updateSettings, addCustomTheme, resetTheme }}>
            {children}
        </ThemeContext.Provider>
    );
};

export const useTheme = () => {
    const context = useContext(ThemeContext);
    if (context === undefined) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};
