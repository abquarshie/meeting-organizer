// The words shown for the values stored in the database (which stay in English, as the Python side expects them).
// Pass a translator for the whole message tree: useTranslations() in the browser, getTranslations() on the server.
type T = (key: string) => string;

const ROLE: Record<string, string> = {
  "Chairman": "role.chairman", "Prayer": "role.prayer", "Treasures Talk": "role.treasures_talk",
  "Spiritual Gems": "role.gems", "Bible Reading": "role.bible_reading", "Initial Presentation": "role.initial",
  "Making Disciples": "role.disciples", "Explaining Beliefs": "role.beliefs", "Student Talk": "role.student_talk",
  "Living Part": "role.living", "Bible Study Conductor": "role.cbs", "Reader": "role.reader",
  "Aux Classroom Counselor": "role.aux_counselor",
};
const SECTION: Record<string, string> = {
  Opening: "sec.opening", Treasures: "sec.treasures", Ministry: "sec.ministry", Living: "sec.living", Closing: "sec.closing",
};
const SECTION_SHORT: Record<string, string> = {
  Treasures: "sec.treasures_short", Ministry: "sec.ministry_short", Living: "sec.living_short",
};
const HALL: Record<string, string> = { main_hall: "hall.main", aux_1: "hall.aux1", aux_2: "hall.aux2" };
const CATEGORY: Record<string, string> = { Brother: "cat.brother", Sister: "cat.sister" };
const GROUP: Record<string, string> = { "Child": "grp.child", "Youth": "grp.youth", "New student": "grp.new" };
const DAY: Record<string, string> = {
  Monday: "day.mon", Tuesday: "day.tue", Wednesday: "day.wed", Thursday: "day.thu", Friday: "day.fri",
  Saturday: "day.sat", Sunday: "day.sun",
};
const EVENT: Record<string, string> = { assembly: "ev.assembly", convention: "ev.convention" };
const EVENT_WEEK: Record<string, string> = { assembly: "ev.assembly_week", convention: "ev.convention_week" };
const LANGUAGE: Record<string, string> = { English: "lang.english", Dangme: "lang.dangme" };

const look = (map: Record<string, string>) => (t: T, value: string | null | undefined): string =>
  value && map[value] ? t(map[value]) : value ?? "";

export const roleLabel = look(ROLE);
export const sectionLabel = look(SECTION);
export const sectionShort = look(SECTION_SHORT);
export const hallLabel = look(HALL);
export const categoryLabel = look(CATEGORY);
export const groupLabel = look(GROUP);
export const dayLabel = look(DAY);
export const eventLabel = look(EVENT);
export const eventWeekLabel = look(EVENT_WEEK);
export const languageLabel = look(LANGUAGE);
