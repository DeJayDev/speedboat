import { SetStateAction, useEffect, useState } from "react";
import { useRoute } from "wouter";
import Guild from "../types/guild";
import Infraction from "../types/infractions";

function InfractionTable(props: {infraction: Infraction}) {
  const inf = props.infraction;

  return (
    <table className='table table-striped table-bordered table-hover'>
      <tbody>
        <tr>
          <td>ID</td>
          <td>{inf.id}</td>
        </tr>
        <tr>
          <td>Target User</td>
          <td>@{inf.user.username} ({inf.user.id})</td>
        </tr>
        <tr>
          <td>Actor User</td>
          <td>@{inf.actor.username} ({inf.actor.id})</td>
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

function GuildInfractionInfo(props: {infraction: Infraction}) {
  return (
    <div className='card'>
      <div className='card-header'>Infraction Info</div>
      <div className='card-body'>
        <InfractionTable infraction={props.infraction} />
      </div>
    </div>
  );
}

/*function GuildInfractionsTable(props: {guild: Guild, infraction: Infraction}) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pages, setPages] = useState(0);

  function onFetchData() {
    setLoading(true);

    guild.getInfractions(pages + 1, state.pageSize, state.sorted, state.filtered).then((data) => {
      setData(data);
      setLoading(false);
    });
  }

  return (
    <ReactTable
      data={data}
      columns={[
        { Header: 'ID', accessor: 'id' },
        {
          Header: 'User', columns: [
            { Header: 'ID', accessor: 'user.id', id: 'user_id' },
            {
              Header: 'Tag',
              id: 'user_tag',
              accessor: d => d.user.username + '#' + d.user.discriminator,
              filterable: false,
              sortable: false,
            }
          ]
        },
        {
          Header: 'Actor', columns: [
            { Header: 'ID', accessor: 'actor.id', id: 'actor_id' },
            {
              Header: 'Tag',
              id: 'actor_tag',
              accessor: d => d.actor.username + '#' + d.actor.discriminator,
              filterable: false,
              sortable: false,
            }
          ]
        },
        { Header: 'Created At', accessor: 'created_at', filterable: false },
        { Header: 'Expires At', accessor: 'expires_at', filterable: false },
        { Header: 'Type', accessor: 'type.name', id: 'type' },
        { Header: 'Reason', accessor: 'reason', sortable: false },
        { Header: 'Active', id: 'active', accessor: d => d.active ? 'Active' : 'Inactive', sortable: false, filterable: false },
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
*/

function GuildInfractions() {

  const [match, params] = useRoute("/guilds/:gid/infractions");
  const [guild, setGuild] = useState<Guild>();
  const [infraction, setInfraction] = useState(null);

  useEffect(() => {
    Guild.fromID(params?.gid!!).then(async g => {
      setGuild(g)
    });
  }, [params?.gid]);

  function onSelectInfraction(infraction: any) {
    setInfraction(infraction);
  }

  if (!guild) {
    return <h3>Loading...</h3>;
  }

  return (
    <div className='col-lg-12'>
      <div className='card'>
        <div className='card-header'>Infractions</div>
        <div className='card-body'>
          This is really hard to reimplement, so I'm just not going to implement it :)
        </div>
      </div>
      {infraction && <GuildInfractionInfo infraction={infraction} />}
    </div>
  );

}

export default GuildInfractions;
