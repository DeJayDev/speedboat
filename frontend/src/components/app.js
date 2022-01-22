// noinspection JSValidateTypes

import React, {Component, Fragment, useEffect, useState} from 'react';
import {Redirect, Route, Switch} from 'react-router-dom';
import {globalState} from '../state';
import Topbar from './topbar';
import Dashboard from './dashboard';
import Login from './login';
import GuildOverview from "./guild_overview";
import GuildStats from "./guild_stats";
import GuildConfigEdit from "./guild_config_edit";
import GuildInfractions from "./guild_infractions";

export default function AppWrapper() {

    const [ready, setReady] = useState(globalState.ready)
    const [user, setUser] = useState(globalState.user)

    useEffect(() => {
        globalState.events.on('ready', () => {
            setReady(true);
        })

        globalState.events.on('user.set', () => {
            setUser(user);
        })

        if(user) {
            console.log('User exists, running init')
            globalState.init();
        }

    }, [ready]);

    if (user === null) {
        console.log('Redirecting to login, no user.')
    } else {
        console.log('fuck it, heres state: ' + globalState)
        return "hey :)"
    }

    /*
    if (!this.state.ready) {
      return (
      <div className="card align-middle">
        <div className="card-header">
          <h1 className="font-weight-bold text-center text-primary">Loading...</h1>
        </div>
        <div className="card-body">
          <h1 className="text-center text-primary">This doesn't take long... <sup>(usually)</sup></h1>
        </div>
      </div>);
    }

    if (this.state.ready && (this.state.user === null)) {
      return <Redirect to='/login' />;
    }*/

    return <Fragment>
        <Topbar />
        <Switch>
          <Route exact path='/' component={Dashboard}/>
          <Route path='/login' component={Login}/>
          <Route path='/guilds/:gid' component={authenticatedPage(GuildOverview)}/>
          <Route path='/guilds/:gid/stats' component={authenticatedPage(GuildStats)}/>
          <Route path='/guilds/:gid/config' component={authenticatedPage(GuildConfigEdit)}/>
          <Route path='/guilds/:gid/infractions' component={authenticatedPage(GuildInfractions)}/>
        </Switch>
    </Fragment>

}

function authenticatedPage(Component) {
    const componentName = Component.displayName || Component.name || 'Component'

    return class extends React.Component {
        static displayName = `Route(${componentName})`

        renderPage() {
            return (
                <Component {...this.props} />
            )
        }

        render() {
            if (globalState.user !== null) {
                return this.renderPage()
            } else {
                console.log('User is not logged in, redirecting to login page');
                return <Redirect to='/login'/>
            }
        }
    }
}

