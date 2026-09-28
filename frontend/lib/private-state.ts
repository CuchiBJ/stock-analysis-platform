const PRIVATE_QUERY_PREFIX = 'private'
const JOURNAL_STORAGE_PREFIX = 'journal'

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem' | 'key' | 'length'>

function requireUserId(userId: string): string {
  const normalized = userId.trim()
  if (!normalized) throw new Error('A user id is required for private browser state')
  return normalized
}

function browserStorage(): StorageLike | null {
  return typeof window === 'undefined' ? null : window.localStorage
}

export function privateQueryKey(userId: string, ...parts: readonly unknown[]) {
  return [PRIVATE_QUERY_PREFIX, requireUserId(userId), ...parts] as const
}

export function journalStorageKey(userId: string, name: string): string {
  const normalizedName = name.trim()
  if (!normalizedName) throw new Error('A journal storage name is required')
  return `${JOURNAL_STORAGE_PREFIX}:${requireUserId(userId)}:${normalizedName}`
}

export function readJournalStorage(
  userId: string,
  name: string,
  storage: StorageLike | null = browserStorage(),
): string | null {
  return storage?.getItem(journalStorageKey(userId, name)) ?? null
}

export function writeJournalStorage(
  userId: string,
  name: string,
  value: string,
  storage: StorageLike | null = browserStorage(),
): void {
  if (!storage) return
  const key = journalStorageKey(userId, name)
  if (value) storage.setItem(key, value)
  else storage.removeItem(key)
}

export function clearUserPrivateStorage(
  userId: string,
  storage: StorageLike | null = browserStorage(),
): void {
  if (!storage) return
  const prefix = `${JOURNAL_STORAGE_PREFIX}:${requireUserId(userId)}:`
  const keys: string[] = []
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index)
    if (key?.startsWith(prefix)) keys.push(key)
  }
  keys.forEach(key => storage.removeItem(key))
}
