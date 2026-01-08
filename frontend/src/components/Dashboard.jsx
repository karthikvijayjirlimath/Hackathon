import { useState } from 'react'
import { Upload, FileText, UserPlus, MagicWand, List } from 'lucide-react'

const UploadCard = ({ title, icon: Icon, color, description, onFileChange }) => (
  <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all group">
    <div className="flex items-center gap-3 mb-4">
      <div className={`p-2 rounded-lg bg-${color}-50 text-${color}-600 group-hover:bg-${color}-100 transition-colors`}>
        <Icon size={20} />
      </div>
      <h3 className="font-bold text-slate-800">{title}</h3>
    </div>
    <div 
      className="border-2 border-dashed border-slate-200 rounded-xl py-8 flex flex-col items-center justify-center cursor-pointer hover:border-primary hover:bg-primary-light transition-all"
      onClick={() => document.getElementById(`input-${title}`).click()}
    >
      <Upload className="text-slate-400 mb-2 group-hover:text-primary transition-colors" size={32} />
      <p className="font-semibold text-sm text-slate-700">Drop files here</p>
      <span className="text-xs text-slate-400">or click to browse</span>
      <input 
        type="file" 
        id={`input-${title}`} 
        className="hidden" 
        multiple 
        onChange={onFileChange}
      />
    </div>
    <p className="mt-3 text-xs text-slate-500 text-center">{description}</p>
  </div>
)

const Dashboard = () => {
  const [patientData, setPatientData] = useState({
    name: '',
    dob: '',
    insurance_policy_id: '',
    email: '',
    refund_bank_account_id: ''
  })

  const handleChange = (e) => {
    setPatientData({ ...patientData, [e.target.name]: e.target.value })
  }

  return (
    <div className="space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <header className="text-center space-y-2">
        <h1 className="text-4xl font-black text-slate-900 tracking-tight">
          Provider <span className="text-primary">Portal</span>
        </h1>
        <p className="text-slate-500 font-medium">Medical Intelligence & Document Analysis</p>
      </header>

      <div className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <UploadCard 
              title="Medical Bills" 
              icon={FileText} 
              color="blue" 
              description="Extract CPT/HCPCS codes & costs"
              onFileChange={() => {}}
            />
            <UploadCard 
              title="Medical Records" 
              icon={FileText} 
              color="emerald" 
              description="Clinical reports & summaries"
              onFileChange={() => {}}
            />
            <UploadCard 
              title="Patient Profile" 
              icon={UserPlus} 
              color="indigo" 
              description="Auto-fill patient information"
              onFileChange={() => {}}
            />
          </div>

          <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm text-center space-y-4">
            <div className="flex items-center justify-center gap-3">
              <List className="text-primary" size={28} />
              <h3 className="text-2xl font-bold text-slate-800">Patient Directory</h3>
            </div>
            <p className="text-slate-500 max-w-md mx-auto">Access and manage all registered patient records and medical intelligence.</p>
            <button className="bg-primary hover:bg-primary-hover text-white px-8 py-3 rounded-xl font-bold flex items-center gap-2 mx-auto transition-all shadow-md shadow-primary/20">
              View Registered Patients
            </button>
          </div>
        </div>

        <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm space-y-6 self-start sticky top-24">
          <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
            <UserPlus className="text-primary" size={24} />
            <h3 className="text-xl font-bold text-slate-800">Manual Entry</h3>
          </div>
          
          <form className="space-y-4">
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Full Name*</label>
              <input 
                name="name"
                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all outline-none text-slate-700"
                placeholder="John Doe"
                value={patientData.name}
                onChange={handleChange}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Date of Birth*</label>
              <input 
                name="dob"
                type="date"
                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all outline-none text-slate-700"
                value={patientData.dob}
                onChange={handleChange}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Insurance ID*</label>
              <input 
                name="insurance_policy_id"
                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all outline-none text-slate-700"
                placeholder="POL-10001"
                value={patientData.insurance_policy_id}
                onChange={handleChange}
              />
            </div>
            <button className="w-full bg-slate-900 hover:bg-slate-800 text-white py-4 rounded-2xl font-bold mt-6 transition-all shadow-lg shadow-slate-200">
              Register Patient
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
