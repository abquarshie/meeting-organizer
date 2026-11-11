// What's new: shown once on each phone or computer when the app opens after an update (components/WhatsNew.tsx).
// Every pull request that changes something you will notice adds an entry at the TOP of NEWS, with the next id,
// today's date and a few plain sentences in English, and in Dangme when you have them (without, the English shows).
// Entries never change id once released.
export type NewsText = { title: string; items: string[] };
export type News = { id: number; date: string; en: NewsText; ada?: NewsText };

export const NEWS: News[] = [
  {
    id: 1, date: "2026-11-11",
    en: {
      title: "Welcome to Meeting Organizer",
      items: [
        "Everything from the Meeting Scheduler for the midweek meeting, for one person.",
        "Switch the screens between English and Dangme in the side menu. Slips and sheets have their own language switch.",
        "Dangme workbooks, the Dangme S-140 and the four-slip Dangme S-89 all work.",
      ],
    },
  },
];
