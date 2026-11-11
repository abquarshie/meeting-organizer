// The fixed lists from pyapp/constants.py. Keep in step with that file: the Python side uses the same names. These are
// the values stored in the database, always in English; lib/labels.ts gives the words shown for them on screen.
export const MIDWEEK = "Midweek Meeting";

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export const CATEGORIES = ["Brother", "Sister"] as const;
export const GROUPS = ["Child", "Youth", "New student"] as const;

export const PRIVILEGES = [
  "Chairman", "Prayer", "Treasures Talk", "Spiritual Gems", "Bible Reading", "Initial Presentation",
  "Making Disciples", "Explaining Beliefs", "Student Talk", "Living Part", "Bible Study Conductor", "Reader",
  "Aux Classroom Counselor",
] as const;
export const ROLES = PRIVILEGES;

/** The slip language: what slips, sheets, the S-140 and the messages are printed in. */
export const LANGUAGES = ["English", "Dangme"] as const;
export type Language = (typeof LANGUAGES)[number];

export const MAIN_HALL = "main_hall";
export const HALLS = ["main_hall", "aux_1", "aux_2"] as const;

export const SECTIONS = ["Opening", "Treasures", "Ministry", "Living", "Closing"] as const;
// Colour carries meaning only: these three mark the workbook sections, as the printed workbook does.
export const SECTION_COLORS: Record<string, string> = {
  Treasures: "#5B6770", Ministry: "#B7821F", Living: "#8E2A2A", Opening: "#8A94A0", Closing: "#8A94A0",
};

export const EVENT_KINDS = ["assembly", "convention"] as const;

export const SAME_ROLE_GAP_DAYS = 10;
export const BACKUP_REMINDER_DAYS = 14;
