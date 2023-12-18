import useStore from "../state";
import GuildsTable from "./Guilds";

function Dashboard() {

  const user = useStore((state) => state.user) // This varible is unused, only to trigger a re-render

  return (
    <div className='card'>
      <div className='card-header'>
        Guilds
      </div>
      <div className='card-body'>
        <GuildsTable />
      </div>
    </div>
  )
}



export default Dashboard;