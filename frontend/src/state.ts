import { create } from 'zustand'
import User from './types/user'

interface Store {
  ready: boolean
  user: User | undefined
  setUser: (user: User | undefined) => void
}

const useStore = create<Store>((set) => ({
  ready: false,
  user: undefined,
  setUser: async (user) => {
    set({ user: (await new User(user as User).create()) })
  },
}));


export default useStore