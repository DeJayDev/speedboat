import { useEffect } from 'react'
import { Route, Switch } from 'wouter'
import Dashboard from './components/Dashboard'
import GuildConfig from './components/GuildConfig'
import GuildOverview from './components/GuildOverview'
import GuildStats from './components/GuildStats'
import Login from './components/Login'
import useStore from './State'
import User from './types/user'
import API from './util'

function App() {

  const user = useStore(state => state.user)
  const setUser = useStore(state => state.setUser)

  useEffect(() => {
    API.get<User>('/users/@me')
      .then(res => {
        let apiUser = new User(res.data as User);
        setUser(apiUser)
      })
      .catch(err => {
        console.log("Error while getting user: " + err)
      })
  }, [setUser])

  return <Switch>
    <Route path='/' component={Dashboard} />
    <Route path='/login' component={Login} />
    <Route path='/guilds/:gid' component={GuildOverview} />
    <Route path='/guilds/:gid/stats' component={GuildStats} />
    <Route path='/guilds/:gid/config' component={GuildConfig} />
  </Switch>
}
export default App
