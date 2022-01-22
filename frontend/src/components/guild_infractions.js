import React, { Component } from 'react';
import debounce from 'lodash/debounce';
import {globalState} from '../state';
import ReactTable from 'react-table-6';

function InfractionTable(props) {
    const inf = this.props.infraction;

    return (
        <table className='table table-striped table-bordered table-hover'>
            <tbody>
            <tr>
                <td>ID</td>
                <td>{inf.id}</td>
            </tr>
            <tr>
                <td>Target User</td>
                <td>{inf.user.username}#{inf.user.discriminator} ({inf.user.id})</td>
            </tr>
            <tr>
                <td>Actor User</td>
                <td>{inf.actor.username}#{inf.actor.discriminator} ({inf.actor.id})</td>
            </tr>
            <tr>
                <td>Created At</td>
                <td>{inf.created_at}</td>
            </tr>
            <tr>
                <td>Expires At</td>
                <td>{inf.expires_at}</td>
            </tr>
            <tr>
                <td>Type</td>
                <td>{inf.type.name}</td>
            </tr>
            <tr>
                <td>Reason</td>
                <td>{inf.reason}</td>
            </tr>
            <tr>
                <td>Messaged?</td>
                <td>{inf.messaged ? 'Yes' : 'No'}</td>
            </tr>
            </tbody>
        </table>
    );
}

function GuildInfractionInfo(props) {
    return (
        <div className='card'>
            <div className='card-header'>Infraction Info</div>
            <div className='card-body'>
                <InfractionTable infraction={props.infraction} />
            </div>
        </div>
    );
}

function GuildInfractionsTable(props) {

    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);

    function onFetchData(state, instance) {
        setLoading(true);

        props.guild.getInfractions(state.page + 1, state.pageSize, state.sorted, state.filtered).then((data) => {
            setData(data);
            setLoading(false);
        });
    }

    return (
        <ReactTable
            data={data}
            columns={[
                {Header: 'ID', accessor: 'id'},
                {Header: 'User', columns: [
                        {Header: 'ID', accessor: 'user.id', id: 'user_id'},
                        {
                            Header: 'Tag',
                            id: 'user_tag',
                            accessor: d => d.user.username + '#' + d.user.discriminator,
                            filterable: false,
                            sortable: false,
                        }
                    ]},
                {Header: 'Actor', columns: [
                        {Header: 'ID', accessor: 'actor.id', id: 'actor_id'},
                        {
                            Header: 'Tag',
                            id: 'actor_tag',
                            accessor: d => d.actor.username + '#' + d.actor.discriminator,
                            filterable: false,
                            sortable: false,
                        }
                    ]},
                {Header: 'Created At', accessor: 'created_at', filterable: false},
                {Header: 'Expires At', accessor: 'expires_at', filterable: false},
                {Header: 'Type', accessor: 'type.name', id: 'type'},
                {Header: 'Reason', accessor: 'reason', sortable: false},
                {Header: 'Active', id: 'active', accessor: d => d.active ? 'Active' : 'Inactive', sortable: false, filterable: false},
            ]}
            pages={10000}
            loading={loading}
            manual
            onFetchData={() => debounce(onFetchData.bind(this), 500)}
            filterable
            className='-striped -highlight'
            getTdProps={(state, rowInfo, column, instance) => {
                return {
                    onClick: () => {
                        props.onSelectInfraction(rowInfo.original);
                    }
                };
            }}
        />
    );
}

export default class GuildInfractions extends Component {
    constructor() {
        super();

        this.state = {
            guild: null,
            infraction: null,
        };
    }

    UNSAFE_componentWillMount() {
        globalState.getGuild(this.props.match.paramsgid).then((guild) => {
            globalState.currentGuild = guild;
            this.setState({guild});
        }).catch((err) => {
            console.error('Failed to load guild', this.props.match.paramsgid);
        });
    }

    componentWillUnmount() {
        globalState.currentGuild = null;
    }

    onSelectInfraction(infraction) {
        console.log('Set infraction', infraction);
        this.setState({infraction});
    }

    render() {
        if (!this.state.guild) {
            return <h3>Loading...</h3>;
        }

        return (
            <div className='col-lg-12'>
                <div className='card'>
                    <div className='card-header'>Infractions</div>
                    <div className='card-body'>
                        <GuildInfractionsTable guild={this.state.guild} onSelectInfraction={this.onSelectInfraction.bind(this)} />
                    </div>
                </div>
                {this.state.infraction && <GuildInfractionInfo infraction={this.state.infraction} />}
            </div>
        );
    }
}
