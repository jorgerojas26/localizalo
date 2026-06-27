"use client";

import { useEffect, useState } from "react";

interface Person {
    person_record_id: string;
    full_name: string;
    given_name?: string | null;
    family_name?: string | null;
    age?: number | null;
    last_known_location?: string | null;
    description?: string | null;
    photo_url?: string | null;
    status: string;
    updated_at?: string | null;
}

type LayoutMode = "grid" | "list";

interface SearchResponse {
    results: Person[];
    error?: string;
}

interface Note {
    note_text: string | null;
    author_name: string | null;
    status: string | null;
    source_date: string | null;
    created_at: string | null;
}

const statusLabel: Record<string, string> = {
    unknown: "Desconocido",
    missing: "Desaparecido",
    found: "Encontrado",
    alive: "Vivo",
    injured: "Herido",
    deceased: "Fallecido",
};

const statusColor: Record<string, string> = {
    unknown: "bg-[#f0f0f3] text-[#60646c]",
    missing: "bg-[#eb8e90]/15 text-[#ab6400]",
    found: "bg-[#16a34a]/10 text-[#16a34a]",
    alive: "bg-[#16a34a]/10 text-[#16a34a]",
    injured: "bg-[#ab6400]/10 text-[#ab6400]",
    deceased: "bg-[#171717]/10 text-[#171717]",
};

export default function Home() {
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<Person[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [layout, setLayout] = useState<LayoutMode>("grid");
    const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);

    useEffect(() => {
        const controller = new AbortController();

        const fetchResults = async () => {
            setIsLoading(true);
            setError(null);

            try {
                const res = await fetch(
                    `/api/search?q=${encodeURIComponent(query)}`,
                    { signal: controller.signal },
                );
                const data: SearchResponse = await res.json();

                if (!res.ok) {
                    throw new Error(data.error ?? "Error al buscar");
                }

                setResults(data.results);
            } catch (err) {
                if (err instanceof DOMException && err.name === "AbortError") {
                    return;
                }
                setError(
                    err instanceof Error ? err.message : "Error desconocido",
                );
            } finally {
                setIsLoading(false);
            }
        };

        const timer = setTimeout(fetchResults, 500);

        return () => {
            clearTimeout(timer);
            controller.abort();
        };
    }, [query]);

    return (
        <div className="flex flex-col min-h-full">
            <header className="h-16 flex items-center border-b border-[#f0f0f3] bg-[#ffffff] sticky top-0 z-10">
                <div className="w-full max-w-3xl mx-auto px-6">
                    <span className="text-[16px] font-semibold tracking-[-0.2px] text-[#171717]">
                        localizalo.org
                    </span>
                </div>
            </header>

            <main className="flex-1">
                <section
                    className="pt-16 pb-12 px-6"
                    style={{
                        background:
                            "radial-gradient(ellipse 80% 60% at 50% -10%, #cfe7ff 0%, #ffffff 70%)",
                    }}
                >
                    <div className="max-w-3xl mx-auto text-center">
                        <h1 className="text-[32px] sm:text-[48px] font-semibold leading-[1.1] tracking-[-1.2px] text-[#171717] mb-4">
                            Encuentra a tu familiar
                        </h1>
                        <p className="text-[16px] leading-[1.5] text-[#60646c] mb-8 max-w-xl mx-auto">
                            Buscador de personas reportadas tras el terremoto de
                            Venezuela 2026.
                        </p>

                        <div className="relative max-w-2xl mx-auto">
                            <div className="absolute left-4 top-1/2 -translate-y-1/2 text-[#999999]">
                                <SearchIcon />
                            </div>
                            <input
                                type="text"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                placeholder="Busca por nombre o ubicación..."
                                className="w-full h-[56px] pl-12 pr-4 text-[18px] bg-[#ffffff] text-[#171717] rounded-[8px] border border-[#dcdee0] outline-none shadow-sm transition-all placeholder:text-[#999999] focus:border-[#171717] focus:ring-2 focus:ring-[#171717]/10"
                                aria-label="Buscar personas"
                            />
                        </div>

                        <div className="mt-3 flex items-center justify-center gap-3 text-[13px] text-[#999999]">
                            <span>
                                {isLoading
                                    ? "Buscando..."
                                    : `${results.length} resultado${results.length === 1 ? "" : "s"}`}
                            </span>
                            {results.length > 0 && (
                                <div className="flex items-center gap-1 border-l border-[#dcdee0] pl-3">
                                    <button
                                        onClick={() => setLayout("grid")}
                                        className={`p-1.5 rounded-[6px] transition-colors ${
                                            layout === "grid"
                                                ? "bg-[#f0f0f3] text-[#171717]"
                                                : "text-[#999999] hover:text-[#60646c]"
                                        }`}
                                        aria-label="Vista cuadrícula"
                                    >
                                        <GridIcon />
                                    </button>
                                    <button
                                        onClick={() => setLayout("list")}
                                        className={`p-1.5 rounded-[6px] transition-colors ${
                                            layout === "list"
                                                ? "bg-[#f0f0f3] text-[#171717]"
                                                : "text-[#999999] hover:text-[#60646c]"
                                        }`}
                                        aria-label="Vista lista"
                                    >
                                        <ListIcon />
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </section>

                <section className="px-6 pb-24">
                    <div className="max-w-3xl mx-auto">
                        {error && (
                            <div className="mb-6 rounded-[12px] border border-[#eb8e90]/40 bg-[#eb8e90]/10 p-4 text-[#171717]">
                                <p className="text-[14px] font-medium">
                                    Algo salió mal
                                </p>
                                <p className="text-[14px] text-[#60646c] mt-1">
                                    {error}
                                </p>
                            </div>
                        )}

                        {isLoading && results.length === 0 && (
                            <div
                                className={
                                    layout === "grid"
                                        ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
                                        : "space-y-4"
                                }
                            >
                                {Array.from({ length: 6 }).map((_, i) => (
                                    <div
                                        key={i}
                                        className={`rounded-[12px] border border-[#f0f0f3] bg-[#fafafa] animate-pulse ${
                                            layout === "list"
                                                ? "h-[120px]"
                                                : "h-[280px]"
                                        }`}
                                    />
                                ))}
                            </div>
                        )}

                        {!isLoading && results.length === 0 && !error && (
                            <div className="text-center py-20">
                                <p className="text-[18px] font-semibold text-[#171717]">
                                    No se encontraron resultados
                                </p>
                                <p className="text-[14px] text-[#60646c] mt-2">
                                    Prueba con otro nombre o ubicación.
                                </p>
                            </div>
                        )}

                        {!isLoading && results.length > 0 && (
                            <>
                                {layout === "grid" ? (
                                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                                        {results.map((person) => (
                                            <PersonCard
                                                key={person.person_record_id}
                                                person={person}
                                                layout="grid"
                                                onSelect={setSelectedPerson}
                                            />
                                        ))}
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        {results.map((person) => (
                                            <PersonCard
                                                key={person.person_record_id}
                                                person={person}
                                                layout="list"
                                                onSelect={setSelectedPerson}
                                            />
                                        ))}
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </section>
            </main>

            <footer className="border-t border-[#f0f0f3] bg-[#ffffff] py-8 px-6">
                <div className="max-w-3xl mx-auto text-center text-[13px] text-[#60646c]">
                    localizalo.org · Datos consolidados de múltiples fuentes.
                </div>
            </footer>

            {selectedPerson && (
                <PersonModal
                    person={selectedPerson}
                    onClose={() => setSelectedPerson(null)}
                />
            )}
        </div>
    );
}

function SearchIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
        </svg>
    );
}

function PersonCard({
    person,
    layout,
    onSelect,
}: {
    person: Person;
    layout: LayoutMode;
    onSelect: (p: Person) => void;
}) {
    const photoUrl = person.photo_url;

    if (layout === "grid") {
        return (
            <button
                onClick={() => onSelect(person)}
                className="rounded-[12px] border border-[#dcdee0] bg-[#ffffff] overflow-hidden shadow-[0_2px_8px_rgba(0,0,0,0.03)] transition-shadow hover:shadow-[0_4px_12px_rgba(0,0,0,0.04)] flex flex-col text-left w-full cursor-pointer"
            >
                <div className="aspect-[4/3] bg-[#f0f0f3] overflow-hidden">
                    {photoUrl ? (
                        <img
                            src={photoUrl}
                            alt={person.full_name}
                            className="w-full h-full object-cover"
                            loading="lazy"
                        />
                    ) : (
                        <div className="w-full h-full flex items-center justify-center text-[#999999]">
                            <PhotoPlaceholderIcon />
                        </div>
                    )}
                </div>
                <div className="p-4 flex-1 flex flex-col">
                    <div className="flex items-start justify-between gap-2">
                        <h2 className="text-[15px] font-semibold leading-[1.3] text-[#171717] line-clamp-2">
                            {person.full_name}
                        </h2>
                        <span
                            className={`shrink-0 inline-flex items-center rounded-[9999px] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.5px] ${
                                statusColor[person.status] ??
                                statusColor.unknown
                            }`}
                        >
                            {statusLabel[person.status] ?? person.status}
                        </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[13px] text-[#60646c]">
                        {person.age != null && <span>{person.age} años</span>}
                        {person.last_known_location && (
                            <span className="flex items-center gap-1">
                                <LocationIcon />
                                <span className="truncate">
                                    {person.last_known_location}
                                </span>
                            </span>
                        )}
                    </div>
                    {person.description && (
                        <p className="mt-2 text-[13px] leading-[1.4] text-[#60646c] line-clamp-2">
                            {person.description}
                        </p>
                    )}
                </div>
            </button>
        );
    }

    return (
        <button
            onClick={() => onSelect(person)}
            className="rounded-[12px] border border-[#dcdee0] bg-[#ffffff] overflow-hidden shadow-[0_2px_8px_rgba(0,0,0,0.03)] transition-shadow hover:shadow-[0_4px_12px_rgba(0,0,0,0.04)] flex text-left w-full cursor-pointer"
        >
            <div className="w-24 sm:w-28 shrink-0 bg-[#f0f0f3] overflow-hidden">
                {photoUrl ? (
                    <img
                        src={photoUrl}
                        alt={person.full_name}
                        className="w-full h-full object-cover"
                        loading="lazy"
                    />
                ) : (
                    <div className="w-full h-full flex items-center justify-center text-[#999999]">
                        <PhotoPlaceholderIcon />
                    </div>
                )}
            </div>
            <div className="flex-1 p-4 sm:p-5 flex flex-col min-w-0">
                <div className="flex items-start justify-between gap-3">
                    <h2 className="text-[16px] sm:text-[18px] font-semibold leading-[1.3] text-[#171717]">
                        {person.full_name}
                    </h2>
                    <span
                        className={`shrink-0 inline-flex items-center rounded-[9999px] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.5px] ${
                            statusColor[person.status] ?? statusColor.unknown
                        }`}
                    >
                        {statusLabel[person.status] ?? person.status}
                    </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[14px] text-[#60646c]">
                    {person.age != null && <span>{person.age} años</span>}
                    {person.last_known_location && (
                        <span className="flex items-center gap-1">
                            <LocationIcon />
                            {person.last_known_location}
                        </span>
                    )}
                </div>
                {person.description && (
                    <p className="mt-1.5 text-[14px] leading-[1.5] text-[#60646c] line-clamp-1">
                        {person.description}
                    </p>
                )}
            </div>
        </button>
    );
}

function LocationIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
            <circle cx="12" cy="10" r="3" />
        </svg>
    );
}

function PhotoPlaceholderIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
        </svg>
    );
}

function GridIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <rect x="3" y="3" width="7" height="7" />
            <rect x="14" y="3" width="7" height="7" />
            <rect x="14" y="14" width="7" height="7" />
            <rect x="3" y="14" width="7" height="7" />
        </svg>
    );
}

function PersonModal({
    person,
    onClose,
}: {
    person: Person;
    onClose: () => void;
}) {
    const [notes, setNotes] = useState<Note[]>([]);
    const [notesLoading, setNotesLoading] = useState(true);

    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        document.addEventListener("keydown", handleKey);
        document.body.style.overflow = "hidden";

        const fetchNotes = async () => {
            setNotesLoading(true);
            try {
                const res = await fetch(
                    `/api/notes?person_record_id=${encodeURIComponent(person.person_record_id)}`,
                );
                const data = await res.json();
                if (res.ok) {
                    setNotes(data.notes ?? []);
                }
            } catch {
                // silent
            } finally {
                setNotesLoading(false);
            }
        };
        fetchNotes();

        return () => {
            document.removeEventListener("keydown", handleKey);
            document.body.style.overflow = "";
        };
    }, [person, onClose]);

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
            onClick={onClose}
        >
            <div className="fixed inset-0 bg-[#171717]/60 backdrop-blur-sm" />
            <div
                className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-[16px] bg-[#ffffff] shadow-xl animate-in"
                onClick={(e) => e.stopPropagation()}
            >
                <button
                    onClick={onClose}
                    className="absolute top-3 right-3 z-10 p-2 rounded-[8px] bg-[#ffffff]/90 hover:bg-[#f0f0f3] transition-colors"
                    aria-label="Cerrar"
                >
                    <CloseIcon />
                </button>

                <div className="md:grid md:grid-cols-[2fr_3fr]">
                    <div className="bg-[#f0f0f3]">
                        <div className="aspect-[4/5] md:aspect-auto md:h-full bg-[#f0f0f3] overflow-hidden">
                            {person.photo_url ? (
                                <img
                                    src={person.photo_url}
                                    alt={person.full_name}
                                    className="w-full h-full object-cover"
                                />
                            ) : (
                                <div className="w-full h-full flex items-center justify-center text-[#999999]">
                                    <PhotoPlaceholderIcon />
                                </div>
                            )}
                        </div>
                        <div className="p-5 md:px-5 md:pb-5 md:pt-0 -mt-1">
                            <h2 className="text-[20px] font-semibold leading-[1.2] tracking-[-0.3px] text-[#171717]">
                                {person.full_name}
                            </h2>
                        </div>
                    </div>

                    <div className="p-5 md:p-6">
                        <div className="flex items-start justify-between gap-3 mb-4">
                            <span
                                className={`inline-flex items-center rounded-[9999px] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.5px] ${
                                    statusColor[person.status] ??
                                    statusColor.unknown
                                }`}
                            >
                                {statusLabel[person.status] ?? person.status}
                            </span>
                        </div>

                        <div className="space-y-4">
                            <div className="space-y-3">
                                {(person.given_name || person.family_name) && (
                                    <DetailRow
                                        label="Nombres"
                                        value={[person.given_name, person.family_name]
                                            .filter(Boolean)
                                            .join(" ")}
                                    />
                                )}
                                {person.age != null && (
                                    <DetailRow
                                        label="Edad"
                                        value={`${person.age} años`}
                                    />
                                )}
                                {person.last_known_location && (
                                    <DetailRow
                                        label="Última ubicación"
                                        value={person.last_known_location}
                                        icon={<LocationIcon />}
                                    />
                                )}
                                {person.description && (
                                    <div>
                                        <span className="text-[11px] font-semibold uppercase tracking-[0.8px] text-[#999999] block mb-1.5">
                                            Descripción
                                        </span>
                                        <p className="text-[14px] leading-[1.6] text-[#60646c]">
                                            {person.description}
                                        </p>
                                    </div>
                                )}
                                {person.updated_at && (
                                    <DetailRow
                                        label="Actualizado"
                                        value={new Date(
                                            person.updated_at,
                                        ).toLocaleDateString("es-ES", {
                                            year: "numeric",
                                            month: "long",
                                            day: "numeric",
                                            hour: "2-digit",
                                            minute: "2-digit",
                                        })}
                                    />
                                )}
                            </div>

                            <hr className="border-[#f0f0f3]" />

                            <div>
                                <div className="flex items-center gap-1.5 mb-3">
                                    <NotesIcon />
                                    <span className="text-[11px] font-semibold uppercase tracking-[0.8px] text-[#999999]">
                                        Notas
                                    </span>
                                </div>
                                <div className="min-h-[128px]">
                                    {notesLoading ? (
                                        <div className="space-y-2">
                                            {Array.from({ length: 2 }).map((_, i) => (
                                                <div
                                                    key={i}
                                                    className="h-[60px] rounded-[8px] bg-[#fafafa] animate-pulse"
                                                />
                                            ))}
                                        </div>
                                    ) : notes.length === 0 ? (
                                        <p className="text-[13px] text-[#999999] italic">
                                            Sin notas
                                        </p>
                                    ) : (
                                        <div className="space-y-2">
                                            {notes.map((note, i) => (
                                                <div
                                                    key={i}
                                                    className="rounded-[8px] border border-[#f0f0f3] bg-[#fafafa] p-3"
                                                >
                                                    {note.note_text && (
                                                        <p className="text-[13px] leading-[1.5] text-[#60646c] whitespace-pre-wrap">
                                                            {note.note_text}
                                                        </p>
                                                    )}
                                                    <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-[#999999]">
                                                        {note.author_name && (
                                                            <span>
                                                                {note.author_name}
                                                            </span>
                                                        )}
                                                        {note.status && (
                                                            <span
                                                                className={`inline-flex items-center rounded-[9999px] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.5px] ${
                                                                    statusColor[note.status] ??
                                                                    statusColor.unknown
                                                                }`}
                                                            >
                                                                {statusLabel[note.status] ??
                                                                    note.status}
                                                            </span>
                                                        )}
                                                        {note.source_date && (
                                                            <span>
                                                                {new Date(
                                                                    note.source_date,
                                                                ).toLocaleDateString(
                                                                    "es-ES",
                                                                )}
                                                            </span>
                                                        )}
                                                        {note.created_at && (
                                                            <span className="ml-auto">
                                                                {new Date(
                                                                    note.created_at,
                                                                ).toLocaleDateString(
                                                                    "es-ES",
                                                                    {
                                                                        day: "numeric",
                                                                        month: "short",
                                                                        hour: "2-digit",
                                                                        minute: "2-digit",
                                                                    },
                                                                )}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function DetailRow({
    label,
    value,
    icon,
    mono,
}: {
    label: string;
    value: string;
    icon?: React.ReactNode;
    mono?: boolean;
}) {
    return (
        <div>
            <span className="text-[11px] font-semibold uppercase tracking-[0.8px] text-[#999999] block mb-1">
                {label}
            </span>
            <span
                className={`text-[14px] text-[#171717] flex items-center gap-1.5 ${mono ? "font-mono text-[13px]" : ""}`}
            >
                {icon && (
                    <span className="text-[#999999] shrink-0">{icon}</span>
                )}
                {value}
            </span>
        </div>
    );
}

function NotesIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
        </svg>
    );
}

function CloseIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <path d="M18 6 6 18" />
            <path d="m6 6 12 12" />
        </svg>
    );
}

function ListIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
    );
}
