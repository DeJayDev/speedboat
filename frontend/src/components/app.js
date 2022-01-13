import React, { useEffect } from 'react';

import {globalState} from '../state';
import Topbar from './topbar';
import Dashboard from './dashboard';
import Login from './login';
import GuildOverview from './guild_overview';
import GuildConfigEdit from './guild_config_edit';
import GuildInfractions from './guild_infractions';
import GuildStats from './guild_stats';
import { BrowserRouter, Route, Switch, Redirect } from 'react-router-dom';

function AppWrapper(props) {

  const [ready, setReady] = React.useState(globalState.ready);
  const [user, setUser] = React.useState(null);

  useEffect(() => {
    if (!globalState.ready) {
      globalState.events.on('ready', () => {
        setReady(true);
      });

      globalState.events.on('user.set', (user) => {
        setUser(user);
      });

      globalState.init();
    }
  }, []);

  if (!ready) {
    return (
    <div className='card align-middle'>
      <div className='card-header'>
        <h1 className='font-weight-bold text-center text-primary'>Loading...</h1>
      </div>
      <div className='card-body'>
        <h1 className='text-center text-primary'>This doesn't take long... <sup>(usually)</sup></h1>
      </div>
    </div>);
  }

  if (ready && user == null) {
    return <Redirect to='/login' />;
  }

  return (
    <div id='content-wrapper'>
      <Topbar />
      <props.view params={props.params}/>
    </div>
  );
}

function wrapped(component) {
  function result(props) {
    return <AppWrapper view={component} params={props.match.params} />;
  }
  return result;
}

export default function router() {
  return (
    <BrowserRouter>
      <Switch>
        <Route exact path='/login' component={Login} />
        <Route exact path='/guilds/:gid/stats' component={wrapped(GuildStats)} />
        <Route exact path='/guilds/:gid/infractions' component={wrapped(GuildInfractions)} />
        <Route exact path='/guilds/:gid/config' component={wrapped(GuildConfigEdit)} />
        <Route exact path='/guilds/:gid' component={wrapped(GuildOverview)} />
        <Route exact path='/' component={wrapped(Dashboard)} />
      </Switch>
    </BrowserRouter>
  );
}
