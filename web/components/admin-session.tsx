"use client";
import {createContext,useContext} from "react";
import {useRemote} from "@/lib/client";
const AdminContext=createContext({authenticated:false,refresh:async()=>{}});
export function AdminSession({children}:{children:React.ReactNode}){
 const {data,refresh}=useRemote<{authenticated:boolean}>("auth/session");
 return <AdminContext.Provider value={{authenticated:!!data?.authenticated,refresh}}>{children}</AdminContext.Provider>;
}
export function useAdmin(){return useContext(AdminContext).authenticated}
export function useSessionRefresh(){return useContext(AdminContext).refresh}
