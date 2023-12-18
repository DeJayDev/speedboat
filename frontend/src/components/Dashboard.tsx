import { Title } from "@tremor/react";
import useStore from "../state";
import GuildsTable from "./Guilds";

function Dashboard() {

  const user = useStore((state) => state.user)

  return (<>
    <div className="flex items-center gap-3 m-2">
      <div className="avatar">
        <div className="w-12 rounded-full">
          <img src={user?.avatarURL} />
        </div>
      </div>
      <Title>Hi {user?.username}!</Title>
    </div>
    
    <GuildsTable/>
  </>)
}



export default Dashboard;